import asyncio
import shlex
import os
import re

def sanitize_string_for_logging(text):
    """
    Sanitize a string to mask any tokens that might be present.
    Looks for JWT-like tokens (long base64 strings with dots).
    """
    if not text:
        return text
    
    text_str = str(text)
    # Pattern to match JWT tokens: long strings with dots that look like base64
    # JWT tokens are typically 200+ characters and contain 2 dots
    jwt_pattern = r'\b([A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,})\b'
    
    def mask_token(match):
        token = match.group(1)
        if len(token) > 20:
            return f"{token[:8]}...{token[-4:]}"
        return "***MASKED***"
    
    sanitized = re.sub(jwt_pattern, mask_token, text_str)
    return sanitized

def sanitize_command_for_logging(command):
    """
    Sanitize command to mask sensitive information like tokens.
    Returns both sanitized command array and sanitized string.
    """
    sanitized_cmd = []
    prev_was_token = False
    
    for arg in command:
        arg_str = str(arg)
        # Check if previous argument was --token
        if prev_was_token:
            # Mask the token value
            if len(arg_str) > 20:
                sanitized_cmd.append(f"{arg_str[:8]}...{arg_str[-4:]}")
            else:
                sanitized_cmd.append("***MASKED***")
            prev_was_token = False
        elif arg_str == "--token" or arg_str == "-t":
            sanitized_cmd.append(arg_str)
            prev_was_token = True
        else:
            # Check if this looks like a JWT token (long base64-like string)
            # JWT tokens are typically very long and contain dots
            if len(arg_str) > 100 and '.' in arg_str and re.match(r'^[A-Za-z0-9._-]+$', arg_str):
                # Likely a JWT token, mask it
                sanitized_cmd.append(f"{arg_str[:8]}...{arg_str[-4:]}")
            else:
                sanitized_cmd.append(arg_str)
    
    # Convert to string
    cmd_str = ' '.join(shlex.quote(str(arg)) for arg in sanitized_cmd)
    return sanitized_cmd, cmd_str

# Lock to prevent concurrent oc login operations (prevents kubeconfig file locking issues)
_oc_login_lock = asyncio.Lock()

async def run(command, check=True, capture_output=True, text=True, timeout=300, stdin_devnull=True):
    print()
    print("┌" + "─" * 58 + "┐")
    print("│" + "  COMMAND START".center(58) + "│")
    print()
    # Sanitize command to mask sensitive information like tokens
    _, sanitized_cmd_str = sanitize_command_for_logging(command)
    print(f"{sanitized_cmd_str}")

    # Check if this is an oc login command that needs locking
    is_oc_login = (
        len(command) > 0 and 
        command[0] in ("oc", "kubectl") and 
        len(command) > 1 and 
        command[1] == "login"
    )
    
    try:
        # Use lock for oc login commands to prevent concurrent kubeconfig writes
        if is_oc_login:
            async with _oc_login_lock:
                return await _execute_command(
                    command, check, capture_output, text, timeout, stdin_devnull, sanitized_cmd_str
                )
        else:
            return await _execute_command(
                command, check, capture_output, text, timeout, stdin_devnull, sanitized_cmd_str
            )
    except RuntimeError:
        # Re-raise RuntimeError as-is (it already has the error message)
        raise
    except Exception as e:
        # Sanitize exception message to mask any tokens
        sanitized_exception_msg = sanitize_string_for_logging(str(e))
        print(f"SnapAPI: DEBUG - Exception during command execution: {type(e).__name__}: {sanitized_exception_msg}")
        # Sanitize command in error message
        _, sanitized_cmd_str = sanitize_command_for_logging(command)
        raise RuntimeError(f"Command '{sanitized_cmd_str}' failed with error: {sanitized_exception_msg}")

async def _execute_command(command, check, capture_output, text, timeout, stdin_devnull, sanitized_cmd_str):
    """Internal function to execute the command."""
    try:
        # Explicitly pass environment to ensure oc/kubectl can find kubeconfig
        # This is especially important for oc commands that need authentication
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL if stdin_devnull else None,
            stdout=asyncio.subprocess.PIPE if capture_output else None,
            stderr=asyncio.subprocess.PIPE if capture_output else None,
            env=os.environ.copy()  # Explicitly pass environment variables
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            try:
                await process.communicate()
            finally:
                print(f"SnapAPI: DEBUG - Command timed out after {timeout}s, killed process.")
                _, sanitized_cmd_str = sanitize_command_for_logging(command)
                raise RuntimeError(f"Command '{sanitized_cmd_str}' timed out after {timeout}s")
        
        if check and process.returncode != 0:
            error_msg = stderr.decode() if stderr else ''
            # Sanitize error message to mask any tokens that might be present
            sanitized_error_msg = sanitize_string_for_logging(error_msg)
            print(f"SnapAPI: DEBUG - Command failed with returncode {process.returncode}, error: {sanitized_error_msg[:500]}")
            # Sanitize command in error message
            _, sanitized_cmd_str = sanitize_command_for_logging(command)
            raise RuntimeError(
                f"Command '{sanitized_cmd_str}' failed with error: {sanitized_error_msg}"
            )
            
        if text and capture_output:
            stdout = stdout.decode() if stdout else ''
            stderr = stderr.decode() if stderr else ''
        
        print()
        print("│" + "  COMMAND COMPLETED".center(58) + "│")
        print("└" + "─" * 58 + "┘")
        print()

        # Store sanitized command string in result
        _, sanitized_cmd_str = sanitize_command_for_logging(command)
        return AsyncProcessResult(
            process.returncode,
            stdout,
            stderr,
            sanitized_cmd_str
        )
    except RuntimeError:
        raise

class AsyncProcessResult:
    def __init__(self, returncode, stdout, stderr, args):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.args = args