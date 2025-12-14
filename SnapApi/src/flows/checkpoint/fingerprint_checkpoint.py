"""
Forensic Checkpoint Fingerprinting Use Case

This use case generates a deterministic forensic fingerprint from a CRIU container checkpoint.
The fingerprint can be used as a baseline to detect drift, tampering, or code injection
by comparing against production checkpoints.
"""

import os
import hashlib
import json
import logging
import tarfile
import tempfile
import asyncio
import difflib
import math
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Union
from pydantic import BaseModel
from datetime import datetime
from flows.proccess_utils import run

logger = logging.getLogger("automation_api")

# Cache for crit availability check to avoid deadlocks from concurrent subprocess calls
_crit_available_cache: Optional[bool] = None
_crit_check_lock = asyncio.Lock()

# Semaphore to limit concurrent crit decode subprocess calls (prevent deadlocks)
_crit_decode_semaphore = asyncio.Semaphore(4)  # Allow max 4 concurrent crit decode calls


class FingerprintCheckpointRequest(BaseModel):
    """Request model for fingerprint checkpoint operation"""
    pod_name: str
    checkpoint_name: str
    keep_extracted_folder: bool = False  # If True, keep the extracted checkpoint folder for inspection
    force_regenerate: bool = False  # If True, regenerate fingerprint even if cached version exists


class FingerprintCheckpointResponse(BaseModel):
    """Response model for fingerprint checkpoint operation"""
    success: bool
    fingerprint: str
    checkpoint_path: str
    file_size: int
    forensic_data: Dict[str, Any]
    extracted_folder_path: Optional[str] = None  # Path to extracted folder if kept
    message: Optional[str] = None


class CompareCheckpointsRequest(BaseModel):
    """Request model for comparing two checkpoints"""
    pod_name_1: str
    checkpoint_name_1: str
    pod_name_2: str
    checkpoint_name_2: str


class CompareCheckpointsResponse(BaseModel):
    """Response model for comparing two checkpoints"""
    success: bool
    checkpoint_1_fingerprint: str
    checkpoint_2_fingerprint: str
    are_identical: bool
    differences: Dict[str, Any]
    message: Optional[str] = None


def canonicalize_json(data: Any) -> str:
    """
    Canonicalize JSON data by sorting keys and ensuring consistent formatting.
    
    Args:
        data: JSON-serializable data
        
    Returns:
        Canonicalized JSON string
    """
    return json.dumps(data, sort_keys=True, separators=(',', ':'))


def make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert bytes objects to base64-encoded strings for JSON serialization.
    
    Args:
        obj: Any object that may contain bytes
        
    Returns:
        Object with bytes converted to base64 strings
    """
    if isinstance(obj, bytes):
        # Convert bytes to base64 string
        return base64.b64encode(obj).decode('utf-8')
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(make_json_serializable(item) for item in obj)
    elif isinstance(obj, set):
        return {make_json_serializable(item) for item in obj}
    else:
        # For other types, return as-is (int, str, float, bool, None, etc.)
        return obj


def hash_string(content: str) -> str:
    """Compute SHA256 hash of a string."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def hash_file(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


async def check_crit_available() -> bool:
    """
    Check if crit command is available in the system.
    
    Uses caching and locking to prevent deadlocks from concurrent subprocess calls.
    
    Returns:
        True if crit is available, False otherwise
    """
    global _crit_available_cache
    
    # Return cached result if available
    if _crit_available_cache is not None:
        return _crit_available_cache
    
    # Use lock to ensure only one check happens at a time
    async with _crit_check_lock:
        # Double-check after acquiring lock (another coroutine might have set it)
        if _crit_available_cache is not None:
            return _crit_available_cache
        
        try:
            cmd = ['which', 'crit']
            result = await run(cmd, check=False, capture_output=True, text=True)
            _crit_available_cache = result.returncode == 0 and result.stdout.strip() != ''
            return _crit_available_cache
        except Exception:
            _crit_available_cache = False
            return False


async def decode_criu_image(img_path: Path) -> Optional[Dict[str, Any]]:
    """
    Decode a CRIU image file using crit decode.
    
    Args:
        img_path: Path to the .img file
        
    Returns:
        Decoded JSON data or None if decoding fails
    """
    try:
        if not img_path.exists():
            return None
        
        # Check file permissions and try to fix if needed
        try:
            if img_path.stat().st_size == 0:
                return None
        except (OSError, PermissionError) as e:
            logger.warning(f"Cannot access {img_path}: {str(e)}. Attempting to fix permissions...")
            try:
                os.chmod(img_path, 0o644)
            except Exception:
                logger.warning(f"Could not fix permissions for {img_path}")
                return None
        
        # Check if crit is available
        crit_available = await check_crit_available()
        if not crit_available:
            logger.warning(f"crit command not available. Cannot decode CRIU images. Please install crit (part of CRIU tools).")
            return None
        
        # Use semaphore to limit concurrent crit decode calls
        async with _crit_decode_semaphore:
            cmd = ['crit', 'decode', '-i', str(img_path)]
            result = await run(cmd, check=False, capture_output=True, text=True)
        
        if result.returncode != 0:
            stderr_str = str(result.stderr)
            # Check if it's a "command not found" error
            if 'No such file or directory' in stderr_str or 'command not found' in stderr_str.lower():
                logger.warning(f"crit command not found. Please install crit (part of CRIU tools) to decode CRIU images.")
            # Check if it's a raw data file (like pages.img) that can't be decoded
            elif 'Unknown magic' in stderr_str or 'raw data' in stderr_str.lower() or 'pages.img' in stderr_str.lower():
                # This is expected for raw memory page files - they can't be decoded, only hashed
                logger.debug(f"File {img_path.name} contains raw data and cannot be decoded with crit (this is expected for pages.img files). Will use raw file hash instead.")
            else:
                logger.warning(f"Failed to decode {img_path}: {result.stderr}")
            return None
        
        # Parse JSON output
        try:
            decoded_data = json.loads(result.stdout)
            return decoded_data
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from {img_path}: {str(e)}")
            return None
            
    except (OSError, PermissionError) as e:
        logger.warning(f"Permission error accessing {img_path}: {str(e)}")
        # Try to fix permissions and retry once
        try:
            os.chmod(img_path, 0o644)
            # Check crit availability before retry
            crit_available = await check_crit_available()
            if crit_available:
                # Retry the decode with semaphore protection
                async with _crit_decode_semaphore:
                    cmd = ['crit', 'decode', '-i', str(img_path)]
                    result = await run(cmd, check=False, capture_output=True, text=True)
                if result.returncode == 0:
                    try:
                        decoded_data = json.loads(result.stdout)
                        return decoded_data
                    except json.JSONDecodeError:
                        return None
        except Exception:
            pass
        return None
    except Exception as e:
        logger.warning(f"Error decoding {img_path}: {str(e)}")
        return None


async def hash_criu_image(img_path: Path, component_name: str, return_decoded: bool = False) -> Union[Optional[str], Tuple[Optional[str], Optional[Dict[str, Any]]]]:
    """
    Decode and hash a CRIU image file.
    
    If crit is not available or the file contains raw data (like pages.img), 
    falls back to hashing the raw file content.
    
    Args:
        img_path: Path to the .img file
        component_name: Name of the component for logging
        return_decoded: If True, returns tuple (hash, decoded_data). If False, returns just hash.
        
    Returns:
        If return_decoded=False: SHA256 hash of canonicalized decoded JSON, or raw file hash if crit unavailable or file is raw data
        If return_decoded=True: Tuple of (hash, decoded_data) where decoded_data may be None
    """
    decoded = await decode_criu_image(img_path)
    if decoded is None:
        # Fallback: hash the raw file if decoding failed
        # This is expected for files like pages.img which contain raw memory page data
        # and cannot be decoded with crit decode
        if img_path.exists():
            logger.debug(f"Using raw file hash for {component_name}: {img_path.name} (file cannot be decoded - may contain raw data)")
            try:
                hash_result = hash_file(img_path)
                return (hash_result, None) if return_decoded else hash_result
            except Exception as e:
                logger.warning(f"Failed to hash raw file {img_path}: {str(e)}")
                return (None, None) if return_decoded else None
        return (None, None) if return_decoded else None
    
    canonical = canonicalize_json(decoded)
    hash_result = hash_string(canonical)
    return (hash_result, decoded) if return_decoded else hash_result


async def hash_filesystem_diff(rootfs_diff_path: Path) -> Optional[str]:
    """
    Hash filesystem changes from rootfs-diff.tar.
    
    For each regular file in the tar:
    - Compute sha256(content)
    - Build sorted list of "path | size | sha256"
    - Hash the combined list
    
    Args:
        rootfs_diff_path: Path to rootfs-diff.tar
        
    Returns:
        SHA256 hash of filesystem diff, or None if file doesn't exist
    """
    if not rootfs_diff_path.exists():
        return None
    
    try:
        # Fix permissions if needed
        try:
            os.chmod(rootfs_diff_path, 0o644)
        except (OSError, PermissionError):
            pass
        
        file_entries = []
        
        with tarfile.open(rootfs_diff_path, 'r:*') as tar:
            for member in tar.getmembers():
                if member.isfile():
                    # Extract file content
                    file_obj = tar.extractfile(member)
                    if file_obj:
                        content = file_obj.read()
                        file_hash = hashlib.sha256(content).hexdigest()
                        file_entries.append(f"{member.name}|{member.size}|{file_hash}")
        
        # Sort entries for deterministic ordering
        file_entries.sort()
        
        # Combine all entries and hash
        combined = '\n'.join(file_entries)
        return hash_string(combined)
        
    except (OSError, PermissionError) as e:
        logger.warning(f"Permission error processing rootfs-diff.tar: {str(e)}")
        return None
    except Exception as e:
        logger.warning(f"Error processing rootfs-diff.tar: {str(e)}")
        return None


async def process_checkpoint_directory(checkpoint_dir: Path, parent_dir: Path = None, include_contents: bool = True) -> Dict[str, Any]:
    """
    Process a CRIU checkpoint directory and generate hashes for all components.
    
    Note: Some components may be None if:
    - The corresponding CRIU image file doesn't exist in the checkpoint
    - The file exists but is empty (0 bytes)
    - The file exists but cannot be decoded/read
    
    Args:
        checkpoint_dir: Path to the checkpoint directory (contains .img files)
        parent_dir: Path to the parent directory (contains config.dump, spec.dump, etc.)
                   If None, uses checkpoint_dir's parent
        include_contents: If True, also store the decoded content of each component
        
    Returns:
        Dictionary with 'hashes' mapping component names to their hashes,
        and optionally 'contents' mapping component names to their decoded content
    """
    logger.info(f"Processing checkpoint directory: {checkpoint_dir}")
    if not checkpoint_dir.exists():
        logger.error(f"Checkpoint directory does not exist: {checkpoint_dir}")
        return {}
    
    # Use parent_dir if provided, otherwise use checkpoint_dir's parent
    if parent_dir is None:
        parent_dir = checkpoint_dir.parent
    
    logger.info(f"Using parent directory for config files: {parent_dir}")
    
    hashes = {}
    contents = {} if include_contents else None
    missing_files = []
    
    # Define CRIU image files to process
    # Note: Some files may have numeric suffixes (e.g., fdinfo-2.img, ids-1.img)
    # CRIU checkpoints can contain various image files with different naming patterns
    criu_images = {
        'process_tree': ['pstree.img'],
        'memory_mm': ['mm-*.img'],
        'memory_pages': ['pages-*.img', 'pagemap-*.img', 'core-*.img'],
        'files': ['files.img', 'fs-*.img'],
        'fdinfo': ['fdinfo.img', 'fdinfo-*.img'],
        'mountpoints': ['mountpoints-*.img'],
        'bind_mounts': ['bind.mounts'],  # This file is typically in parent directory
        'ids': ['ids.img', 'ids-*.img'],
        'netns': ['netns-*.img'],
        'ipcns': ['ipcns-*.img'],
        'seccomp': ['seccomp.img'],
        'cgroup': ['cgroup.img'],
        'utsns': ['utsns-*.img', 'timens-*.img'],
        'inventory': ['inventory.img'],
    }
    
    # Process CRIU image files
    for component_name, patterns in criu_images.items():
        found = False
        for pattern in patterns:
            # Handle wildcards
            if '*' in pattern:
                # Search recursively in subdirectories
                matches = list(checkpoint_dir.rglob(pattern))
                if not matches:
                    # Also try non-recursive
                    matches = list(checkpoint_dir.glob(pattern))
                if matches:
                    logger.info(f"Found {len(matches)} matches for {component_name} pattern {pattern}: {[m.name for m in matches]}")
                    # Process all matches and combine
                    component_hashes = []
                    component_contents_list = []
                    for match in sorted(matches):
                        logger.info(f"Processing {component_name}: {match.name} (path: {match})")
                        # Decode once and reuse for both hash and content
                        need_decoded = include_contents and contents is not None
                        result = await hash_criu_image(match, component_name, return_decoded=need_decoded)
                        if need_decoded:
                            img_hash, decoded = result
                        else:
                            img_hash = result
                            decoded = None
                        
                        if img_hash:
                            component_hashes.append(f"{match.name}:{img_hash}")
                            logger.info(f"Successfully hashed {component_name}: {match.name} -> {img_hash[:16]}...")
                            # Store decoded content if available
                            if decoded is not None:
                                component_contents_list.append({match.name: decoded})
                        else:
                            logger.warning(f"Failed to hash {component_name}: {match.name} (hash_criu_image returned None)")
                    if component_hashes:
                        combined = '\n'.join(component_hashes)
                        hashes[component_name] = hash_string(combined)
                        if include_contents and contents is not None and component_contents_list:
                            # Store all decoded contents for this component
                            contents[component_name] = component_contents_list if len(component_contents_list) > 1 else component_contents_list[0] if component_contents_list else None
                        found = True
                        logger.info(f"Successfully processed {component_name} with {len(component_hashes)} file(s)")
                        break
                    else:
                        logger.warning(f"Pattern {pattern} matched files for {component_name} but none could be hashed")
            else:
                # Try exact match first in checkpoint_dir
                img_path = checkpoint_dir / pattern
                if not img_path.exists():
                    # For bind.mounts, also check parent directory
                    if pattern == 'bind.mounts':
                        img_path = parent_dir / pattern
                        if img_path.exists():
                            logger.info(f"Found {component_name} file in parent directory: {img_path}")
                    else:
                        # Try recursive search
                        recursive_matches = list(checkpoint_dir.rglob(pattern))
                        if recursive_matches:
                            img_path = recursive_matches[0]
                            logger.info(f"Found {component_name} file recursively: {img_path}")
                
                if img_path.exists():
                    logger.info(f"Found {component_name} file: {img_path.name} (path: {img_path})")
                    # For bind.mounts, hash as raw file (not a CRIU image)
                    if pattern == 'bind.mounts':
                        try:
                            hashes[component_name] = hash_file(img_path)
                            logger.info(f"Successfully hashed {component_name}")
                            found = True
                            break
                        except Exception as e:
                            logger.warning(f"Failed to hash bind.mounts: {str(e)}")
                    else:
                        # Decode once and reuse for both hash and content
                        need_decoded = include_contents and contents is not None
                        result = await hash_criu_image(img_path, component_name, return_decoded=need_decoded)
                        if need_decoded:
                            img_hash, decoded = result
                        else:
                            img_hash = result
                            decoded = None
                        
                        if img_hash:
                            hashes[component_name] = img_hash
                            # Store decoded content if available
                            if decoded is not None:
                                contents[component_name] = decoded
                            logger.info(f"Successfully hashed {component_name}")
                            found = True
                            break
                else:
                    logger.debug(f"{component_name} file not found: {checkpoint_dir / pattern}")
        
        if not found:
            hashes[component_name] = None
            missing_files.append(component_name)
            logger.debug(f"No files found for {component_name}")
    
    if missing_files:
        logger.info(f"Components not found in checkpoint: {', '.join(missing_files)}")
    
    # Process container config files (these are typically in the parent directory)
    spec_dump = parent_dir / 'spec.dump'
    if not spec_dump.exists():
        # Fallback to checkpoint_dir
        spec_dump = checkpoint_dir / 'spec.dump'
    if spec_dump.exists():
        try:
            # Fix permissions if needed
            try:
                os.chmod(spec_dump, 0o644)
            except (OSError, PermissionError):
                pass
            
            with open(spec_dump, 'r') as f:
                spec_data = json.load(f)
            canonical = canonicalize_json(spec_data)
            hashes['container_spec'] = hash_string(canonical)
            if include_contents and contents is not None:
                contents['container_spec'] = spec_data
            logger.info("Successfully processed container_spec from spec.dump")
        except (OSError, PermissionError) as e:
            logger.warning(f"Permission error processing spec.dump: {str(e)}")
            hashes['container_spec'] = None
            missing_files.append('container_spec')
        except Exception as e:
            logger.warning(f"Error processing spec.dump: {str(e)}")
            hashes['container_spec'] = None
            missing_files.append('container_spec')
    else:
        hashes['container_spec'] = None
        logger.debug("spec.dump not found in checkpoint")
    
    config_dump = parent_dir / 'config.dump'
    if not config_dump.exists():
        # Fallback to checkpoint_dir
        config_dump = checkpoint_dir / 'config.dump'
    if config_dump.exists():
        try:
            # Fix permissions if needed
            try:
                os.chmod(config_dump, 0o644)
            except (OSError, PermissionError):
                pass
            
            with open(config_dump, 'r') as f:
                config_data = json.load(f)
            canonical = canonicalize_json(config_data)
            hashes['container_config'] = hash_string(canonical)
            if include_contents and contents is not None:
                contents['container_config'] = config_data
            logger.info("Successfully processed container_config from config.dump")
        except (OSError, PermissionError) as e:
            logger.warning(f"Permission error processing config.dump: {str(e)}")
            hashes['container_config'] = None
            missing_files.append('container_config')
        except Exception as e:
            logger.warning(f"Error processing config.dump: {str(e)}")
            hashes['container_config'] = None
            missing_files.append('container_config')
    else:
        hashes['container_config'] = None
        logger.debug("config.dump not found in checkpoint")
    
    # Process filesystem diff (typically in parent directory)
    rootfs_diff = parent_dir / 'rootfs-diff.tar'
    if not rootfs_diff.exists():
        # Fallback to checkpoint_dir
        rootfs_diff = checkpoint_dir / 'rootfs-diff.tar'
    if rootfs_diff.exists():
        diff_hash = await hash_filesystem_diff(rootfs_diff)
        if diff_hash:
            hashes['rootfs_diff'] = diff_hash
            # Store content if requested
            if include_contents and contents is not None:
                try:
                    # Extract metadata about the rootfs-diff.tar contents
                    with tarfile.open(rootfs_diff, 'r:*') as tar:
                        members = tar.getmembers()
                        rootfs_content = {
                            'file_count': len(members),
                            'files': [{'name': m.name, 'size': m.size, 'type': m.type} for m in members[:100]],  # Limit to first 100 files
                            'total_size': sum(m.size for m in members),
                            'tar_path': str(rootfs_diff)
                        }
                        # If there are more files, indicate that
                        if len(members) > 100:
                            rootfs_content['note'] = f'Showing first 100 of {len(members)} files'
                    contents['rootfs_diff'] = rootfs_content
                    logger.info("Successfully processed rootfs_diff from rootfs-diff.tar")
                except Exception as e:
                    logger.warning(f"Failed to extract rootfs_diff content: {str(e)}")
                    # Store at least that it exists
                    contents['rootfs_diff'] = {'exists': True, 'tar_path': str(rootfs_diff), 'error': str(e)}
            logger.info("Successfully processed rootfs_diff from rootfs-diff.tar")
        else:
            hashes['rootfs_diff'] = None
            logger.debug("rootfs-diff.tar exists but could not be processed")
    else:
        hashes['rootfs_diff'] = None
        logger.debug("rootfs-diff.tar not found in checkpoint (no filesystem changes)")
    
    # Process additional checkpoint metadata files (typically in parent directory)
    # dump.log - CRIU dump log file
    dump_log = parent_dir / 'dump.log'
    if not dump_log.exists():
        # Fallback to checkpoint_dir
        dump_log = checkpoint_dir / 'dump.log'
    if dump_log.exists():
        try:
            try:
                os.chmod(dump_log, 0o644)
            except (OSError, PermissionError):
                pass
            # Hash the dump log content
            hashes['dump_log'] = hash_file(dump_log)
            logger.info("Successfully processed dump_log")
        except Exception as e:
            logger.warning(f"Error processing dump.log: {str(e)}")
            hashes['dump_log'] = None
    else:
        hashes['dump_log'] = None
        logger.debug("dump.log not found in checkpoint")
    
    # stats-dump - Statistics dump file (typically in parent directory)
    stats_dump = parent_dir / 'stats-dump'
    if not stats_dump.exists():
        # Fallback to checkpoint_dir
        stats_dump = checkpoint_dir / 'stats-dump'
    if stats_dump.exists():
        try:
            try:
                os.chmod(stats_dump, 0o644)
            except (OSError, PermissionError):
                pass
            # Hash the stats dump content
            hashes['stats_dump'] = hash_file(stats_dump)
            logger.info("Successfully processed stats_dump")
        except Exception as e:
            logger.warning(f"Error processing stats-dump: {str(e)}")
            hashes['stats_dump'] = None
    else:
        hashes['stats_dump'] = None
        logger.debug("stats-dump not found in checkpoint")
    
    # io.kubernetes.cri-o.LogPath - CRI-O log path file (typically in parent directory)
    log_path_file = parent_dir / 'io.kubernetes.cri-o.LogPath'
    if not log_path_file.exists():
        # Fallback to checkpoint_dir
        log_path_file = checkpoint_dir / 'io.kubernetes.cri-o.LogPath'
    if log_path_file.exists():
        try:
            try:
                os.chmod(log_path_file, 0o644)
            except (OSError, PermissionError):
                pass
            # Hash the log path file content
            hashes['crio_log_path'] = hash_file(log_path_file)
            logger.info("Successfully processed crio_log_path")
        except Exception as e:
            logger.warning(f"Error processing io.kubernetes.cri-o.LogPath: {str(e)}")
            hashes['crio_log_path'] = None
    else:
        hashes['crio_log_path'] = None
        logger.debug("io.kubernetes.cri-o.LogPath not found in checkpoint")
    
    # Extract environment variables from process tree if available
    if include_contents and contents is not None and 'process_tree' in contents:
        try:
            env_vars = extract_environment_variables(contents.get('process_tree'))
            if env_vars:
                contents['environment_variables'] = env_vars
                # Also hash environment variables separately
                env_canonical = canonicalize_json(env_vars)
                hashes['environment_variables'] = hash_string(env_canonical)
                logger.info("Successfully extracted environment variables from process tree")
        except Exception as e:
            logger.warning(f"Failed to extract environment variables: {str(e)}")
    
    # Return both hashes and contents
    result = {"hashes": hashes}
    if include_contents and contents is not None:
        result["contents"] = contents
    return result


# ============================================================================
# Structured Data Extraction Functions
# ============================================================================

def extract_process_tree_details(pstree_data: Any) -> Dict[str, Any]:
    """
    Extract structured process tree information from decoded pstree.img.
    
    Returns:
        Dictionary with:
        - processes: List of processes with PID, PPID, command line
        - added_processes: List of new processes (for comparison)
        - removed_processes: List of removed processes (for comparison)
        - pid_changes: List of PID changes
        - ppid_changes: List of PPID changes
        - cmdline_changes: List of command line changes
    """
    if not pstree_data or not isinstance(pstree_data, dict):
        return {}
    
    processes = []
    
    # Extract process information from pstree structure
    # CRIU pstree structure varies, but typically contains entries array
    entries = pstree_data.get('entries', [])
    if not entries:
        # Try alternative structure
        entries = pstree_data.get('pstree', {}).get('entries', [])
    
    for entry in entries:
        if isinstance(entry, dict):
            pid = entry.get('pid') or entry.get('item', {}).get('pid')
            ppid = entry.get('ppid') or entry.get('item', {}).get('ppid')
            # Command line might be in different places
            cmdline = entry.get('cmdline') or entry.get('item', {}).get('comm') or entry.get('comm')
            if isinstance(cmdline, list):
                cmdline = ' '.join(cmdline)
            
            processes.append({
                'pid': pid,
                'ppid': ppid,
                'cmdline': cmdline or '',
                'full_entry': entry  # Keep full entry for reference
            })
    
    return {
        'processes': processes,
        'process_count': len(processes)
    }


def extract_memory_map_details(mm_data: Any) -> Dict[str, Any]:
    """
    Extract structured memory map information from decoded mm-*.img.
    
    Returns:
        Dictionary with:
        - vmas: List of VMAs with permissions, offsets, sizes
        - new_vmas: List of new VMAs (for comparison)
        - removed_vmas: List of removed VMAs (for comparison)
        - permission_changes: List of permission changes
        - offset_changes: List of offset changes
        - size_changes: List of size changes
    """
    if not mm_data or not isinstance(mm_data, dict):
        return {}
    
    vmas = []
    
    # Extract VMA information
    # CRIU mm structure typically has vmas array
    vma_list = mm_data.get('vmas', [])
    if not vma_list:
        vma_list = mm_data.get('mm', {}).get('vmas', [])
    
    for vma in vma_list:
        if isinstance(vma, dict):
            vmas.append({
                'start': vma.get('start'),
                'end': vma.get('end'),
                'size': (vma.get('end') or 0) - (vma.get('start') or 0),
                'prot': vma.get('prot'),  # Permissions (rwx)
                'flags': vma.get('flags'),
                'offset': vma.get('pgoff'),  # Page offset
                'file': vma.get('file'),  # File-backed mapping
                'shmid': vma.get('shmid'),  # Shared memory ID
                'full_vma': vma
            })
    
    return {
        'vmas': vmas,
        'vma_count': len(vmas)
    }


def extract_file_descriptor_details(fdinfo_data: Any) -> Dict[str, Any]:
    """
    Extract structured file descriptor information from decoded fdinfo-*.img.
    
    Returns:
        Dictionary with:
        - file_descriptors: List of FDs with socket state, file offsets
        - new_fds: List of new file descriptors (for comparison)
        - closed_fds: List of closed file descriptors (for comparison)
        - socket_state_changes: List of socket state changes
        - offset_changes: List of file offset changes
    """
    if not fdinfo_data:
        return {}
    
    # Handle both single fdinfo and array of fdinfo
    fd_list = fdinfo_data if isinstance(fdinfo_data, list) else [fdinfo_data]
    
    file_descriptors = []
    for fd_entry in fd_list:
        if isinstance(fd_entry, dict):
            fd = fd_entry.get('fd') or fd_entry.get('id')
            fd_type = fd_entry.get('type')
            
            fd_info = {
                'fd': fd,
                'type': fd_type,
                'full_entry': fd_entry
            }
            
            # Extract socket-specific information
            if fd_type == 'socket' or 'socket' in str(fd_type).lower():
                fd_info['socket_state'] = fd_entry.get('state')
                fd_info['socket_family'] = fd_entry.get('family')
                fd_info['socket_type'] = fd_entry.get('type')
                fd_info['socket_protocol'] = fd_entry.get('protocol')
            
            # Extract file-specific information
            if 'file' in str(fd_type).lower() or fd_entry.get('pos'):
                fd_info['file_offset'] = fd_entry.get('pos') or fd_entry.get('offset')
                fd_info['file_path'] = fd_entry.get('name') or fd_entry.get('path')
            
            file_descriptors.append(fd_info)
    
    return {
        'file_descriptors': file_descriptors,
        'fd_count': len(file_descriptors)
    }


def extract_environment_variables(pstree_data: Any) -> Dict[str, Any]:
    """
    Extract environment variables from process tree data.
    
    Returns:
        Dictionary mapping process PID to its environment variables
    """
    if not pstree_data:
        return {}
    
    env_vars_by_process = {}
    
    # Handle different pstree structures
    entries = []
    if isinstance(pstree_data, dict):
        entries = pstree_data.get('entries', []) or pstree_data.get('pstree', {}).get('entries', [])
    elif isinstance(pstree_data, list):
        entries = pstree_data
    
    for entry in entries:
        if isinstance(entry, dict):
            pid = entry.get('pid') or entry.get('item', {}).get('pid')
            # Environment variables might be in different places
            env = entry.get('env') or entry.get('environ') or entry.get('item', {}).get('env')
            
            if env:
                if isinstance(env, list):
                    # Convert list format to dict
                    env_dict = {}
                    for env_item in env:
                        if isinstance(env_item, str) and '=' in env_item:
                            key, value = env_item.split('=', 1)
                            env_dict[key] = value
                        elif isinstance(env_item, dict):
                            env_dict.update(env_item)
                    env = env_dict
                elif isinstance(env, dict):
                    pass  # Already in dict format
                else:
                    env = {}
                
                if pid and env:
                    env_vars_by_process[pid] = env
    
    return {
        'by_process': env_vars_by_process,
        'all_variables': {k: v for proc_env in env_vars_by_process.values() for k, v in proc_env.items()},
        'process_count': len(env_vars_by_process)
    }


def calculate_entropy(data: bytes) -> float:
    """
    Calculate Shannon entropy of data.
    
    Returns:
        Entropy value between 0 and 8 (for bytes)
    """
    if not data or len(data) == 0:
        return 0.0
    
    # Count byte frequencies
    frequencies = {}
    for byte in data:
        frequencies[byte] = frequencies.get(byte, 0) + 1
    
    # Calculate entropy
    entropy = 0.0
    data_len = len(data)
    for count in frequencies.values():
        probability = count / data_len
        if probability > 0:
            entropy -= probability * math.log2(probability)
    
    return entropy


def assess_component_risk(component: str, diff: Dict[str, Any], detailed_analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Assess security risk level for a component difference.
    
    Args:
        component: Component name
        diff: Difference data for the component
        detailed_analysis: Optional detailed analysis from comparison
        
    Returns:
        Dictionary with risk_level, risk_score, risk_category, and findings
    """
    risk_level = "info"  # Default: info, low, medium, high, critical
    risk_score = 0  # 0-100
    risk_category = "operational"  # operational, security, performance, configuration
    findings = []
    
    component_lower = component.lower()
    status = diff.get("status", "")
    
    # Critical risk components
    critical_components = [
        "process_tree", "memory_mm", "memory_pages", 
        "seccomp", "cgroup", "environment_variables"
    ]
    
    # High risk components
    high_risk_components = [
        "fdinfo", "netns", "files", "rootfs_diff",
        "container_spec", "container_config"
    ]
    
    # Check for process tree changes (critical security risk)
    if component == "process_tree":
        risk_category = "security"
        if detailed_analysis:
            added = detailed_analysis.get("added_processes", [])
            removed = detailed_analysis.get("removed_processes", [])
            changed = detailed_analysis.get("changed_processes", [])
            
            if added:
                # Check for suspicious process additions
                suspicious_patterns = ["sh", "bash", "nc", "netcat", "python", "perl", "wget", "curl"]
                for proc in added:
                    cmdline = str(proc.get("cmdline", "")).lower()
                    for pattern in suspicious_patterns:
                        if pattern in cmdline:
                            risk_level = "critical"
                            risk_score = 95
                            findings.append({
                                "type": "suspicious_process_added",
                                "severity": "critical",
                                "message": f"Suspicious process added: {proc.get('cmdline', 'unknown')}",
                                "pid": proc.get("pid")
                            })
                            break
                
                if risk_level != "critical":
                    risk_level = "high"
                    risk_score = 75
                    findings.append({
                        "type": "processes_added",
                        "severity": "high",
                        "message": f"{len(added)} new process(es) detected",
                        "count": len(added)
                    })
            
            if removed:
                risk_level = "medium" if risk_level == "info" else risk_level
                risk_score = max(risk_score, 50)
                findings.append({
                    "type": "processes_removed",
                    "severity": "medium",
                    "message": f"{len(removed)} process(es) terminated",
                    "count": len(removed)
                })
            
            if changed:
                risk_level = "medium" if risk_level == "info" else risk_level
                risk_score = max(risk_score, 45)
                findings.append({
                    "type": "processes_changed",
                    "severity": "medium",
                    "message": f"{len(changed)} process(es) modified",
                    "count": len(changed)
                })
        else:
            # No detailed analysis, but process tree changed - high risk
            risk_level = "high"
            risk_score = 70
            findings.append({
                "type": "process_tree_changed",
                "severity": "high",
                "message": "Process tree structure changed (detailed analysis unavailable)"
            })
    
    # Check for memory map changes (critical - potential code injection)
    elif component == "memory_mm":
        risk_category = "security"
        if detailed_analysis:
            new_vmas = detailed_analysis.get("new_vmas", [])
            changed_vmas = detailed_analysis.get("changed_vmas", [])
            
            if new_vmas:
                # Check for executable memory regions
                exec_vmas = [v for v in new_vmas if v.get("prot") and "x" in str(v.get("prot")).lower()]
                if exec_vmas:
                    risk_level = "critical"
                    risk_score = 90
                    findings.append({
                        "type": "executable_memory_added",
                        "severity": "critical",
                        "message": f"{len(exec_vmas)} new executable memory region(s) detected - possible code injection",
                        "count": len(exec_vmas)
                    })
                else:
                    risk_level = "high"
                    risk_score = 65
                    findings.append({
                        "type": "memory_regions_added",
                        "severity": "high",
                        "message": f"{len(new_vmas)} new memory region(s) mapped",
                        "count": len(new_vmas)
                    })
            
            if changed_vmas:
                # Permission changes are critical
                perm_changes = [v for v in changed_vmas if "permissions" in v.get("changes", {})]
                if perm_changes:
                    risk_level = "critical"
                    risk_score = 85
                    findings.append({
                        "type": "memory_permissions_changed",
                        "severity": "critical",
                        "message": f"Memory permission changes detected - possible privilege escalation",
                        "count": len(perm_changes)
                    })
        else:
            risk_level = "high"
            risk_score = 65
            findings.append({
                "type": "memory_map_changed",
                "severity": "high",
                "message": "Memory map structure changed"
            })
    
    # Check for file descriptor changes (high risk - network/IO)
    elif component == "fdinfo":
        risk_category = "security"
        if detailed_analysis:
            new_fds = detailed_analysis.get("new_fds", [])
            # Check for new network sockets
            new_sockets = [fd for fd in new_fds if fd.get("type") == "socket" or "socket" in str(fd.get("type", "")).lower()]
            if new_sockets:
                risk_level = "high"
                risk_score = 75
                findings.append({
                    "type": "new_network_connections",
                    "severity": "high",
                    "message": f"{len(new_sockets)} new network socket(s) opened",
                    "count": len(new_sockets)
                })
            elif new_fds:
                risk_level = "medium"
                risk_score = 50
                findings.append({
                    "type": "file_descriptors_added",
                    "severity": "medium",
                    "message": f"{len(new_fds)} new file descriptor(s)",
                    "count": len(new_fds)
                })
        else:
            risk_level = "medium"
            risk_score = 50
            findings.append({
                "type": "file_descriptors_changed",
                "severity": "medium",
                "message": "File descriptor state changed"
            })
    
    # Check for environment variable changes (high risk - config injection)
    elif component == "environment_variables":
        risk_category = "security"
        if detailed_analysis:
            added_vars = detailed_analysis.get("added_variables", {})
            changed_vars = detailed_analysis.get("changed_variables", {})
            
            # Check for sensitive env vars
            sensitive_vars = ["password", "secret", "key", "token", "credential", "api_key", "auth"]
            sensitive_added = {k: v for k, v in added_vars.items() 
                              if any(sens in k.lower() for sens in sensitive_vars)}
            
            if sensitive_added:
                risk_level = "critical"
                risk_score = 90
                findings.append({
                    "type": "sensitive_env_vars_added",
                    "severity": "critical",
                    "message": f"Sensitive environment variables added: {', '.join(sensitive_added.keys())}",
                    "variables": list(sensitive_added.keys())
                })
            elif added_vars:
                risk_level = "high"
                risk_score = 60
                findings.append({
                    "type": "environment_variables_added",
                    "severity": "high",
                    "message": f"{len(added_vars)} environment variable(s) added",
                    "count": len(added_vars)
                })
            
            if changed_vars:
                sensitive_changed = {k: v for k, v in changed_vars.items() 
                                   if any(sens in k.lower() for sens in sensitive_vars)}
                if sensitive_changed:
                    risk_level = "critical" if risk_level != "critical" else "critical"
                    risk_score = max(risk_score, 85)
                    findings.append({
                        "type": "sensitive_env_vars_changed",
                        "severity": "critical",
                        "message": f"Sensitive environment variables modified: {', '.join(sensitive_changed.keys())}",
                        "variables": list(sensitive_changed.keys())
                    })
        else:
            risk_level = "high"
            risk_score = 60
            findings.append({
                "type": "environment_variables_changed",
                "severity": "high",
                "message": "Environment variables changed"
            })
    
    # Check for filesystem changes (medium-high risk)
    elif component == "rootfs_diff":
        risk_category = "security"
        risk_level = "high"
        risk_score = 70
        findings.append({
            "type": "filesystem_changes",
            "severity": "high",
            "message": "Filesystem changes detected - possible file modification or injection"
        })
    
    # Check for container config changes (high risk)
    elif component in ["container_spec", "container_config"]:
        risk_category = "security"
        risk_level = "high"
        risk_score = 75
        findings.append({
            "type": "container_config_changed",
            "severity": "high",
            "message": f"Container {component} modified - possible configuration tampering"
        })
    
    # Check for security-related components
    elif component == "seccomp":
        risk_category = "security"
        risk_level = "high"
        risk_score = 80
        findings.append({
            "type": "seccomp_changed",
            "severity": "high",
            "message": "Seccomp security profile changed - possible security policy modification"
        })
    
    elif component == "cgroup":
        risk_category = "security"
        risk_level = "medium"
        risk_score = 55
        findings.append({
            "type": "cgroup_changed",
            "severity": "medium",
            "message": "Cgroup configuration changed"
        })
    
    # Network namespace changes
    elif component == "netns":
        risk_category = "security"
        risk_level = "high"
        risk_score = 70
        findings.append({
            "type": "network_namespace_changed",
            "severity": "high",
            "message": "Network namespace configuration changed"
        })
    
    # Missing component in one checkpoint
    elif status == "missing_in_one":
        risk_category = "operational"
        risk_level = "medium"
        risk_score = 40
        findings.append({
            "type": "component_missing",
            "severity": "medium",
            "message": f"Component {component} missing in one checkpoint"
        })
    
    # Default for other components
    else:
        if component in critical_components:
            risk_level = "high"
            risk_score = 65
        elif component in high_risk_components:
            risk_level = "medium"
            risk_score = 50
        else:
            risk_level = "low"
            risk_score = 30
        
        findings.append({
            "type": "component_changed",
            "severity": risk_level,
            "message": f"Component {component} changed"
        })
    
    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_category": risk_category,
        "findings": findings,
        "component": component
    }


def analyze_memory_pages(pages_data: Any) -> Dict[str, Any]:
    """
    Analyze memory pages for entropy, shared pages, and differences.
    
    Returns:
        Dictionary with:
        - page_count: Total number of pages
        - high_entropy_pages: Pages with high entropy (potentially sensitive)
        - shared_pages: Shared memory pages
        - page_analysis: Detailed page analysis
    """
    if not pages_data:
        return {}
    
    # This is a placeholder - actual implementation would need to parse page data
    # CRIU pages format is complex and binary, would need specialized parsing
    
    return {
        'note': 'Memory page analysis requires specialized parsing of CRIU page format',
        'data_available': pages_data is not None
    }


async def extract_checkpoint_tar(tar_path: Path) -> Path:
    """
    Extract checkpoint tar file to a temporary directory.
    
    Args:
        tar_path: Path to the checkpoint .tar file
        
    Returns:
        Path to the extracted directory
    """
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Extract tar file in a thread to avoid blocking the event loop
        def extract_tar_sync():
            """Synchronous tar extraction function to run in thread."""
            with tarfile.open(tar_path, 'r:*') as tar:
                members = tar.getmembers()
                logger.info(f"Tar file contains {len(members)} members")
                # Log first 20 members
                for i, member in enumerate(members[:20]):
                    logger.debug(f"  {i+1}. {member.name} (size: {member.size}, type: {member.type})")
                if len(members) > 20:
                    logger.debug(f"  ... and {len(members) - 20} more")
                
                tar.extractall(path=temp_dir)
        
        # Run tar extraction in thread pool to avoid blocking
        await asyncio.to_thread(extract_tar_sync)
        
        # Fix permissions on extracted files to ensure they're readable
        # This is necessary because some tar files may have restrictive permissions
        def fix_permissions(path):
            """Recursively fix permissions on extracted files and directories."""
            try:
                # Make directory readable and accessible
                if path.is_dir():
                    os.chmod(path, 0o755)
                    # Recursively fix permissions for all children
                    for root, dirs, files in os.walk(path):
                        try:
                            os.chmod(root, 0o755)
                            for d in dirs:
                                try:
                                    os.chmod(os.path.join(root, d), 0o755)
                                except (OSError, PermissionError):
                                    pass
                            for f in files:
                                try:
                                    os.chmod(os.path.join(root, f), 0o644)
                                except (OSError, PermissionError):
                                    pass
                        except (OSError, PermissionError) as e:
                            logger.warning(f"Could not fix permissions for {root}: {str(e)}")
                elif path.is_file():
                    os.chmod(path, 0o644)
            except (OSError, PermissionError) as e:
                logger.warning(f"Could not fix permissions for {path}: {str(e)}")
        
        # Fix permissions for the entire extracted directory in thread to avoid blocking
        try:
            await asyncio.to_thread(fix_permissions, temp_dir)
        except Exception as e:
            logger.warning(f"Error fixing permissions: {str(e)}")
        
        # Checkpoint directory might be at root or in a 'checkpoint' subdirectory
        checkpoint_dir = temp_dir / 'checkpoint'
        if not checkpoint_dir.exists():
            checkpoint_dir = temp_dir
        
        # Log directory structure for debugging
        logger.info(f"Extracted checkpoint directory: {checkpoint_dir}")
        if checkpoint_dir.exists():
            files_list = list(checkpoint_dir.iterdir())
            logger.info(f"Files in checkpoint directory ({len(files_list)}): {[f.name for f in files_list[:20]]}")
            # Look for .img files specifically
            img_files = list(checkpoint_dir.glob('*.img'))
            logger.info(f"Found {len(img_files)} .img files: {[f.name for f in img_files[:10]]}")
        
        return checkpoint_dir
        
    except Exception as e:
        # Cleanup on error
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise Exception(f"Failed to extract checkpoint: {str(e)}")


async def get_component_content(
    checkpoint_dir: Path,
    parent_dir: Path,
    component_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get the decoded content of a specific component from a checkpoint.
    
    Args:
        checkpoint_dir: Path to the checkpoint directory
        parent_dir: Path to the parent directory (for config files)
        component_name: Name of the component to retrieve
        
    Returns:
        Decoded JSON content of the component, or None if not found
    """
    # Map component names to file patterns and search directories
    component_map = {
        'process_tree': ('pstree.img', 'checkpoint', True),
        'memory_mm': ('mm-*.img', 'checkpoint', True),
        'memory_pages': ('pages-*.img', 'checkpoint', True),
        'files': ('files.img', 'checkpoint', True),
        'fdinfo': ('fdinfo-*.img', 'checkpoint', True),
        'mountpoints': ('mountpoints-*.img', 'checkpoint', True),
        'bind_mounts': ('bind.mounts', 'parent', False),
        'ids': ('ids-*.img', 'checkpoint', True),
        'netns': ('netns-*.img', 'checkpoint', True),
        'ipcns': ('ipcns-*.img', 'checkpoint', True),
        'seccomp': ('seccomp.img', 'checkpoint', True),
        'cgroup': ('cgroup.img', 'checkpoint', True),
        'utsns': ('utsns-*.img', 'checkpoint', True),
        'inventory': ('inventory.img', 'checkpoint', True),
        'container_spec': ('spec.dump', 'parent', False),
        'container_config': ('config.dump', 'parent', False),
        'dump_log': ('dump.log', 'parent', False),
        'stats_dump': ('stats-dump', 'parent', False),
        'crio_log_path': ('io.kubernetes.cri-o.LogPath', 'parent', False),
        'rootfs_diff': ('rootfs-diff.tar', 'parent', False),  # Filesystem diff tar file
        'environment_variables': ('process_tree', 'checkpoint', True),  # Extracted from process_tree
    }
    
    if component_name not in component_map:
        logger.warning(f"Unknown component: {component_name}")
        return None
    
    pattern, search_location, is_criu_image = component_map[component_name]
    search_dir = checkpoint_dir if search_location == 'checkpoint' else parent_dir
    
    logger.debug(f"Looking for component {component_name} (pattern: {pattern}, location: {search_location}, search_dir: {search_dir})")
    
    # Find the file - use recursive search for better reliability
    file_path = None
    
    if '*' in pattern:
        # Pattern has wildcard - search recursively
        matches = list(search_dir.rglob(pattern))
        if matches:
            file_path = sorted(matches)[0]  # Use first match
            logger.debug(f"Found {component_name} at {file_path} (wildcard match)")
        else:
            # Also try in checkpoint_dir if we were searching parent_dir
            if search_dir != checkpoint_dir:
                matches = list(checkpoint_dir.rglob(pattern))
                if matches:
                    file_path = sorted(matches)[0]
                    logger.debug(f"Found {component_name} at {file_path} (fallback to checkpoint_dir)")
    else:
        # Exact filename - try multiple locations
        # First try the primary location
        file_path = search_dir / pattern
        if not file_path.exists():
            # Try in checkpoint_dir if we were searching parent_dir
            if search_dir != checkpoint_dir:
                file_path = checkpoint_dir / pattern
                logger.debug(f"Trying {component_name} at {file_path} (fallback to checkpoint_dir)")
        
        # If still not found, try recursive search
        if not file_path.exists():
            matches = list(search_dir.rglob(pattern))
            if matches:
                file_path = sorted(matches)[0]
                logger.debug(f"Found {component_name} at {file_path} (recursive search in search_dir)")
            elif search_dir != checkpoint_dir:
                matches = list(checkpoint_dir.rglob(pattern))
                if matches:
                    file_path = sorted(matches)[0]
                    logger.debug(f"Found {component_name} at {file_path} (recursive search in checkpoint_dir)")
    
    if not file_path or not file_path.exists():
        logger.warning(f"Component {component_name} (pattern: {pattern}) not found in {search_dir} or {checkpoint_dir}")
        # Log directory contents for debugging
        if search_dir.exists():
            try:
                files = list(search_dir.rglob('*'))
                logger.debug(f"Files in {search_dir}: {[str(f.relative_to(search_dir)) for f in files[:20]]}")
            except Exception as e:
                logger.debug(f"Could not list files in {search_dir}: {str(e)}")
        return None
    
    logger.info(f"Found component {component_name} at {file_path}")
    
    try:
        # Fix permissions
        try:
            os.chmod(file_path, 0o644)
        except (OSError, PermissionError):
            pass
        
        if is_criu_image:
            # Decode CRIU image
            return await decode_criu_image(file_path)
        else:
            # Read file based on type
            if file_path.suffix == '.dump':
                with open(file_path, 'r') as f:
                    return json.load(f)
            elif file_path.suffix == '.tar' and 'rootfs-diff' in file_path.name:
                # Handle rootfs-diff.tar - extract metadata about contents
                try:
                    with tarfile.open(file_path, 'r:*') as tar:
                        members = tar.getmembers()
                        return {
                            'file_count': len(members),
                            'files': [{'name': m.name, 'size': m.size, 'type': m.type} for m in members[:200]],  # Limit to first 200 files
                            'total_size': sum(m.size for m in members),
                            'tar_path': str(file_path),
                            'note': f'Showing first 200 of {len(members)} files' if len(members) > 200 else None
                        }
                except Exception as e:
                    logger.warning(f"Error reading rootfs-diff.tar: {str(e)}")
                    return {"error": str(e), "tar_path": str(file_path)}
            elif file_path.name in ['bind.mounts', 'dump.log', 'stats-dump', 'io.kubernetes.cri-o.LogPath']:
                # Read as text file
                with open(file_path, 'r') as f:
                    content = f.read()
                    return {"content": content}
            else:
                return None
    except Exception as e:
        logger.warning(f"Error reading component {component_name} from {file_path}: {str(e)}")
        return None


def generate_unified_diff(content1: Any, content2: Any, component_name: str) -> str:
    """
    Generate a unified diff between two component contents.
    
    Args:
        content1: Content from checkpoint 1 (can be dict, list, or string)
        content2: Content from checkpoint 2 (can be dict, list, or string)
        component_name: Name of the component being compared
        
    Returns:
        Unified diff string in Git-diff style, or a message if contents are identical
    """
    # Handle None cases
    if content1 is None and content2 is None:
        return f"--- checkpoint_1/{component_name}\n+++ checkpoint_2/{component_name}\n@@ -0,0 +0,0 @@\n# Component is missing in both checkpoints\n"
    
    if content1 is None:
        return f"--- checkpoint_1/{component_name}\n+++ checkpoint_2/{component_name}\n@@ -0,0 +1,1 @@\n+# Component is missing in checkpoint 1\n"
    
    if content2 is None:
        return f"--- checkpoint_1/{component_name}\n+++ checkpoint_2/{component_name}\n@@ -1,1 +0,0 @@\n-# Component is missing in checkpoint 2\n"
    
    # Convert both contents to canonical JSON strings
    try:
        str1 = json.dumps(content1, indent=2, sort_keys=True, ensure_ascii=False)
        str2 = json.dumps(content2, indent=2, sort_keys=True, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Error serializing content for diff: {str(e)}")
        return f"--- checkpoint_1/{component_name}\n+++ checkpoint_2/{component_name}\n@@ -0,0 +0,0 @@\n# Error generating diff: {str(e)}\n"
    
    # Check if contents are identical
    if str1 == str2:
        # Return a diff showing they're identical
        lines = str1.splitlines(keepends=True)
        if not lines:
            lines = [""]
        line_count = len(lines)
        return f"--- checkpoint_1/{component_name}\n+++ checkpoint_2/{component_name}\n@@ -1,{line_count} +1,{line_count} @@\n# Contents are identical\n" + ''.join(f" {line}" for line in lines)
    
    # Split into lines
    lines1 = str1.splitlines(keepends=True)
    lines2 = str2.splitlines(keepends=True)
    
    # Generate unified diff
    diff = list(difflib.unified_diff(
        lines1,
        lines2,
        fromfile=f"checkpoint_1/{component_name}",
        tofile=f"checkpoint_2/{component_name}",
        lineterm='',
        n=3  # Context lines
    ))
    
    # If diff is empty (shouldn't happen after identical check, but just in case)
    if not diff:
        return f"--- checkpoint_1/{component_name}\n+++ checkpoint_2/{component_name}\n@@ -0,0 +0,0 @@\n# No differences detected (but contents may differ in whitespace or formatting)\n"
    
    return ''.join(diff)


async def get_component_diff(
    pod_name_1: str,
    checkpoint_name_1: str,
    pod_name_2: str,
    checkpoint_name_2: str,
    component_name: str
) -> Dict[str, Any]:
    """
    Get the content diff for a specific component between two checkpoints.
    
    Args:
        pod_name_1: Pod name for checkpoint 1
        checkpoint_name_1: Checkpoint name for checkpoint 1
        pod_name_2: Pod name for checkpoint 2
        checkpoint_name_2: Checkpoint name for checkpoint 2
        component_name: Name of the component to diff
        
    Returns:
        Dictionary containing diff information
    """
    # Use the same base directory as the routes
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    checkpoint_base_path = os.path.join(BASE_DIR, 'checkpoints')
    
    # Get paths
    checkpoint_dir_1 = Path(checkpoint_base_path) / pod_name_1
    checkpoint_file_1 = checkpoint_dir_1 / checkpoint_name_1
    
    checkpoint_dir_2 = Path(checkpoint_base_path) / pod_name_2
    checkpoint_file_2 = checkpoint_dir_2 / checkpoint_name_2
    
    logger.info(f"Getting component diff for {component_name}")
    logger.info(f"Checkpoint 1: {checkpoint_file_1} (exists: {checkpoint_file_1.exists()})")
    logger.info(f"Checkpoint 2: {checkpoint_file_2} (exists: {checkpoint_file_2.exists()})")
    
    # Try to load content from fingerprint JSON files first (much faster)
    checkpoint_name_1_clean = checkpoint_name_1.replace('.tar', '')
    checkpoint_name_2_clean = checkpoint_name_2.replace('.tar', '')
    fingerprint_file_1 = checkpoint_dir_1 / f"{checkpoint_name_1_clean}_fingerprint.json"
    fingerprint_file_2 = checkpoint_dir_2 / f"{checkpoint_name_2_clean}_fingerprint.json"
    
    content_1 = None
    content_2 = None
    
    # Try to load from fingerprint files
    if fingerprint_file_1.exists():
        try:
            with open(fingerprint_file_1, 'r') as f:
                fingerprint_data_1 = json.load(f)
                contents_1 = fingerprint_data_1.get('contents', {})
                content_1 = contents_1.get(component_name)
                # Handle nested structure (e.g., if content is wrapped in a key)
                if content_1 is None and isinstance(contents_1, dict):
                    # Try to find content in nested structure
                    for key, value in contents_1.items():
                        if component_name in str(key).lower() or (isinstance(value, dict) and component_name in value):
                            content_1 = value.get(component_name) if isinstance(value, dict) else value
                            break
                if content_1 is not None:
                    logger.info(f"Loaded {component_name} content from fingerprint file for checkpoint 1 (type: {type(content_1).__name__})")
                else:
                    logger.debug(f"{component_name} not found in fingerprint cache for checkpoint 1 (available components: {list(contents_1.keys())})")
        except Exception as e:
            logger.warning(f"Failed to load content from fingerprint file 1: {str(e)}")
    
    if fingerprint_file_2.exists():
        try:
            with open(fingerprint_file_2, 'r') as f:
                fingerprint_data_2 = json.load(f)
                contents_2 = fingerprint_data_2.get('contents', {})
                content_2 = contents_2.get(component_name)
                # Handle nested structure (e.g., if content is wrapped in a key)
                if content_2 is None and isinstance(contents_2, dict):
                    # Try to find content in nested structure
                    for key, value in contents_2.items():
                        if component_name in str(key).lower() or (isinstance(value, dict) and component_name in value):
                            content_2 = value.get(component_name) if isinstance(value, dict) else value
                            break
                if content_2 is not None:
                    logger.info(f"Loaded {component_name} content from fingerprint file for checkpoint 2 (type: {type(content_2).__name__})")
                else:
                    logger.debug(f"{component_name} not found in fingerprint cache for checkpoint 2 (available components: {list(contents_2.keys())})")
        except Exception as e:
            logger.warning(f"Failed to load content from fingerprint file 2: {str(e)}")
    
    # If we have both contents from fingerprint files, use them directly
    # Check for content existence: content exists if it's not None and not an error dict
    # Empty dicts/arrays should be considered as having content (they exist, just empty)
    has_content_1 = (
        content_1 is not None and 
        not (isinstance(content_1, dict) and 'error' in content_1 and len(content_1) == 1)
    )
    has_content_2 = (
        content_2 is not None and 
        not (isinstance(content_2, dict) and 'error' in content_2 and len(content_2) == 1)
    )
    
    if has_content_1 and has_content_2:
        logger.info("Using content from fingerprint files (no extraction needed)")
        unified_diff = generate_unified_diff(content_1, content_2, component_name)
        canonical_1 = canonicalize_json(content_1) if content_1 is not None else ""
        canonical_2 = canonicalize_json(content_2) if content_2 is not None else ""
        
        return {
            "component_name": component_name,
            "content_1": content_1,
            "content_2": content_2,
            "canonical_1": canonical_1,
            "canonical_2": canonical_2,
            "unified_diff": unified_diff,
            "has_content_1": has_content_1,  # Use computed value
            "has_content_2": has_content_2,  # Use computed value
            "source": "fingerprint_cache"  # Indicate we used cached content
        }
    
    # If we have at least one, still use cache for that one
    if has_content_1 or has_content_2:
        logger.info(f"Partial content from cache: has_content_1={has_content_1}, has_content_2={has_content_2}, will extract missing one(s)")
    
    # If we have at least one content from cache, use it and only extract the missing one
    if content_1 is not None or content_2 is not None:
        logger.info(f"Partial content from cache: content_1={content_1 is not None}, content_2={content_2 is not None}")
    
    # If we only have one or neither, extract and get content
    # Extract both checkpoints
    extracted_dir_1 = None
    extracted_dir_2 = None
    
    try:
        # Extract checkpoint 1
        if checkpoint_file_1.suffix == '.tar':
            extracted_checkpoint_dir_1 = await extract_checkpoint_tar(checkpoint_file_1)
            checkpoint_dir_1 = extracted_checkpoint_dir_1
            # The extracted checkpoint dir might be at temp_dir/checkpoint or temp_dir
            # If it's temp_dir/checkpoint, spec.dump is in temp_dir (parent)
            # If it's temp_dir itself, spec.dump is in temp_dir (checkpoint_dir itself)
            # So we check: if checkpoint_dir has a 'checkpoint' subdirectory, parent is checkpoint_dir.parent
            # Otherwise, parent is checkpoint_dir itself
            if (checkpoint_dir_1 / 'checkpoint').exists():
                # Checkpoint is at temp_dir/checkpoint, so parent is temp_dir
                parent_dir_1 = checkpoint_dir_1.parent
            else:
                # Checkpoint is at temp_dir itself, so parent is also temp_dir (same as checkpoint_dir)
                parent_dir_1 = checkpoint_dir_1
            logger.info(f"Checkpoint 1 extracted: checkpoint_dir={checkpoint_dir_1}, parent_dir={parent_dir_1}")
            # Log what files are in parent_dir for debugging
            if parent_dir_1.exists():
                parent_files = [f.name for f in parent_dir_1.iterdir() if f.is_file()][:10]
                logger.info(f"Files in parent_dir_1: {parent_files}")
                # Specifically check for rootfs-diff.tar
                rootfs_diff_file = parent_dir_1 / 'rootfs-diff.tar'
                if rootfs_diff_file.exists():
                    logger.info(f"Found rootfs-diff.tar in parent_dir_1: {rootfs_diff_file}")
                else:
                    logger.debug(f"rootfs-diff.tar not found in parent_dir_1, searching recursively...")
                    rootfs_matches = list(parent_dir_1.rglob('rootfs-diff.tar'))
                    if rootfs_matches:
                        logger.info(f"Found rootfs-diff.tar recursively: {rootfs_matches}")
        else:
            checkpoint_dir_1 = checkpoint_file_1
            parent_dir_1 = checkpoint_dir_1.parent
        
        # Extract checkpoint 2
        if checkpoint_file_2.suffix == '.tar':
            extracted_checkpoint_dir_2 = await extract_checkpoint_tar(checkpoint_file_2)
            checkpoint_dir_2 = extracted_checkpoint_dir_2
            if (checkpoint_dir_2 / 'checkpoint').exists():
                parent_dir_2 = checkpoint_dir_2.parent
            else:
                parent_dir_2 = checkpoint_dir_2
            logger.info(f"Checkpoint 2 extracted: checkpoint_dir={checkpoint_dir_2}, parent_dir={parent_dir_2}")
            if parent_dir_2.exists():
                parent_files = [f.name for f in parent_dir_2.iterdir() if f.is_file()][:10]
                logger.info(f"Files in parent_dir_2: {parent_files}")
                # Specifically check for rootfs-diff.tar
                rootfs_diff_file = parent_dir_2 / 'rootfs-diff.tar'
                if rootfs_diff_file.exists():
                    logger.info(f"Found rootfs-diff.tar in parent_dir_2: {rootfs_diff_file}")
                else:
                    logger.debug(f"rootfs-diff.tar not found in parent_dir_2, searching recursively...")
                    rootfs_matches = list(parent_dir_2.rglob('rootfs-diff.tar'))
                    if rootfs_matches:
                        logger.info(f"Found rootfs-diff.tar recursively: {rootfs_matches}")
        else:
            checkpoint_dir_2 = checkpoint_file_2
            parent_dir_2 = checkpoint_dir_2.parent
        
        # Get component content from both (only if not already loaded from fingerprint)
        logger.info(f"Getting content for component: {component_name}")
        if content_1 is None or (isinstance(content_1, dict) and len(content_1) == 0):
            content_1 = await get_component_content(checkpoint_dir_1, parent_dir_1, component_name)
        if content_2 is None or (isinstance(content_2, dict) and len(content_2) == 0):
            content_2 = await get_component_content(checkpoint_dir_2, parent_dir_2, component_name)
        
        # More robust content detection: empty dicts/arrays should be considered as having content
        has_content_1_final = (
            content_1 is not None and 
            not (isinstance(content_1, dict) and 'error' in content_1 and len(content_1) == 1)
        )
        has_content_2_final = (
            content_2 is not None and 
            not (isinstance(content_2, dict) and 'error' in content_2 and len(content_2) == 1)
        )
        
        logger.info(f"Content 1 found: {has_content_1_final} (content_1 type: {type(content_1).__name__}, is None: {content_1 is None})")
        logger.info(f"Content 2 found: {has_content_2_final} (content_2 type: {type(content_2).__name__}, is None: {content_2 is None})")
        
        # Generate diff
        unified_diff = generate_unified_diff(content_1, content_2, component_name)
        logger.info(f"Generated diff length: {len(unified_diff)} characters")
        
        # Canonicalize for display
        canonical_1 = canonicalize_json(content_1) if content_1 is not None else ""
        canonical_2 = canonicalize_json(content_2) if content_2 is not None else ""
        
        return {
            "component_name": component_name,
            "content_1": content_1,
            "content_2": content_2,
            "canonical_1": canonical_1,
            "canonical_2": canonical_2,
            "unified_diff": unified_diff,
            "has_content_1": has_content_1_final,  # Use robust detection
            "has_content_2": has_content_2_final   # Use robust detection
        }
        
    finally:
        # Cleanup extracted directories
        # Note: We might want to keep them if keep_extracted_folder is True
        # For now, we'll clean them up
        pass


async def fingerprint_checkpoint_use_case(
    request: FingerprintCheckpointRequest
) -> FingerprintCheckpointResponse:
    """
    Generate a deterministic forensic fingerprint from a CRIU container checkpoint.
    
    The fingerprint is computed by:
    1. Extracting the checkpoint tar file
    2. Decoding CRIU image files using crit decode
    3. Canonicalizing and hashing each component
    4. Combining all component hashes into a single fingerprint
    
    Args:
        request: FingerprintCheckpointRequest containing pod_name and checkpoint_name
        
    Returns:
        FingerprintCheckpointResponse with forensic fingerprint and component hashes
        
    Raises:
        FileNotFoundError: If checkpoint file doesn't exist
        Exception: For other errors during fingerprint generation
    """
    extracted_dir = None
    try:
        # Get base directory and checkpoint path
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        checkpoint_dir = os.path.join(BASE_DIR, 'checkpoints', request.pod_name)
        checkpoint_name_clean = request.checkpoint_name.replace('.tar', '')
        checkpoint_file_path = os.path.join(checkpoint_dir, f"{checkpoint_name_clean}.tar")
        
        logger.info(f"Generating forensic fingerprint for checkpoint: {checkpoint_file_path}")
        
        # Check if checkpoint file exists
        if not os.path.exists(checkpoint_file_path):
            raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_file_path}")
        
        # Get file size
        file_size = os.path.getsize(checkpoint_file_path)
        
        # Check for cached fingerprint
        fingerprint_file_path = os.path.join(checkpoint_dir, f"{checkpoint_name_clean}_fingerprint.json")
        cached_fingerprint = None
        
        if not request.force_regenerate and os.path.exists(fingerprint_file_path):
            try:
                logger.info(f"Loading cached fingerprint from: {fingerprint_file_path}")
                # Check file size to detect potential corruption
                file_size = os.path.getsize(fingerprint_file_path)
                if file_size == 0:
                    logger.warning(f"Cached fingerprint file is empty, regenerating...")
                else:
                    with open(fingerprint_file_path, 'r', encoding='utf-8') as f:
                        cached_data = json.load(f)
                    
                    # Verify the cached fingerprint is for the same checkpoint file
                    if cached_data.get('checkpoint_dir') == checkpoint_file_path:
                        cached_fingerprint = cached_data
                        logger.info("Using cached fingerprint")
                    else:
                        logger.info("Cached fingerprint is for a different checkpoint file, regenerating...")
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to load cached fingerprint (corrupted JSON): "
                    f"line {e.lineno}, column {e.colno}: {str(e)}. Regenerating..."
                )
            except Exception as e:
                logger.warning(f"Failed to load cached fingerprint: {str(e)}, regenerating...")
        
        # If we have a valid cached fingerprint, return it
        if cached_fingerprint and not request.force_regenerate:
            return FingerprintCheckpointResponse(
                success=True,
                fingerprint=cached_fingerprint.get('fingerprint', ''),
                checkpoint_path=checkpoint_file_path,
                file_size=file_size,
                forensic_data=cached_fingerprint,
                extracted_folder_path=None,  # Not available from cache
                message="Forensic fingerprint loaded from cache"
            )
        
        # Generate new fingerprint
        logger.info("Generating new forensic fingerprint...")
        
        # Extract checkpoint tar file
        logger.info("Extracting checkpoint tar file...")
        extracted_checkpoint_dir = await extract_checkpoint_tar(Path(checkpoint_file_path))
        extracted_dir = extracted_checkpoint_dir.parent  # Keep reference for cleanup
        
        logger.info(f"Extracted checkpoint directory: {extracted_checkpoint_dir}")
        logger.info(f"Directory exists: {extracted_checkpoint_dir.exists()}")
        
        # Check if crit is available
        crit_available = await check_crit_available()
        if not crit_available:
            logger.warning("crit command not available. Forensic fingerprinting will use raw file hashes instead of decoded CRIU images.")
            logger.warning("For full forensic analysis, please install crit (part of CRIU tools): dnf install criu-tools or apt-get install criu")
        
        # Process checkpoint directory and generate component hashes
        # Pass both checkpoint_dir (for .img files) and extracted_dir (for config files)
        logger.info("Processing checkpoint directory and decoding CRIU images...")
        result = await process_checkpoint_directory(extracted_checkpoint_dir, extracted_dir, include_contents=True)
        component_hashes = result['hashes']
        component_contents = result.get('contents', {})
        
        # Log summary of what was found
        processed_count = sum(1 for v in component_hashes.values() if v is not None)
        logger.info(f"Processed {processed_count} out of {len(component_hashes)} components")
        
        # Build fingerprint from all component hashes
        # Create sorted list of "key=value" entries (excluding None values)
        hash_entries = []
        for key, value in sorted(component_hashes.items()):
            if value is not None:
                hash_entries.append(f"{key}={value}")
        
        # Combine all entries and compute final fingerprint
        combined = '\n'.join(hash_entries)
        fingerprint = hash_string(combined)
        
        # Check crit availability for metadata
        crit_available = await check_crit_available()
        
        # Build forensic data structure
        processed_components = [h for h in component_hashes.values() if h is not None]
        missing_components = [k for k, v in component_hashes.items() if v is None]
        
        forensic_data = {
            "version": 1,
            "checkpoint_dir": str(checkpoint_file_path),
            "hashes": component_hashes,
            "contents": component_contents,  # Store decoded component contents for easy comparison
            "fingerprint": fingerprint,
            "generated_at": datetime.now().isoformat(),
            "components_processed": len(processed_components),
            "components_total": len(component_hashes),
            "components_missing": missing_components,
            "crit_available": crit_available,
            "fingerprint_method": "decoded_criu" if crit_available else "raw_file_hashes",
            "note": "Some components may be None if the corresponding CRIU image files don't exist in the checkpoint, are empty, or cannot be decoded. This is normal and depends on what was checkpointed. Component contents are stored for easy comparison without re-extraction."
        }
        
        # Save fingerprint to a file for future reference (cache)
        # Convert bytes to JSON-serializable format before saving
        try:
            # Make a deep copy and convert bytes to base64 strings
            serializable_forensic_data = make_json_serializable(forensic_data)
            with open(fingerprint_file_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_forensic_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Forensic fingerprint saved to cache: {fingerprint_file_path}")
        except Exception as e:
            logger.warning(f"Failed to save fingerprint file: {str(e)}")
            # Log more details about the error
            import traceback
            logger.warning(f"Traceback: {traceback.format_exc()}")
        
        # Determine if we should keep the extracted folder
        extracted_folder_path = None
        if request.keep_extracted_folder and extracted_dir and extracted_dir.exists():
            extracted_folder_path = str(extracted_dir)
            logger.info(f"Keeping extracted folder as requested: {extracted_folder_path}")
        else:
            # Cleanup extracted directory if not keeping it
            if extracted_dir and extracted_dir.exists():
                import shutil
                try:
                    shutil.rmtree(extracted_dir, ignore_errors=True)
                    logger.debug(f"Cleaned up extracted directory: {extracted_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup extracted directory: {str(e)}")
        
        return FingerprintCheckpointResponse(
            success=True,
            fingerprint=fingerprint,
            checkpoint_path=checkpoint_file_path,
            file_size=file_size,
            forensic_data=forensic_data,
            extracted_folder_path=extracted_folder_path,
            message="Forensic fingerprint generated successfully" + (f" (extracted folder kept at: {extracted_folder_path})" if extracted_folder_path else "")
        )
        
    except FileNotFoundError as e:
        logger.error(f"Checkpoint file not found: {str(e)}")
        # Cleanup on error unless keeping folder was requested
        if not request.keep_extracted_folder and extracted_dir and extracted_dir.exists():
            import shutil
            try:
                shutil.rmtree(extracted_dir, ignore_errors=True)
            except Exception:
                pass
        raise
    except Exception as e:
        logger.error(f"Error generating forensic fingerprint: {str(e)}")
        # Cleanup on error unless keeping folder was requested
        if not request.keep_extracted_folder and extracted_dir and extracted_dir.exists():
            import shutil
            try:
                shutil.rmtree(extracted_dir, ignore_errors=True)
            except Exception:
                pass
        raise Exception(f"Failed to generate forensic fingerprint: {str(e)}")


async def compare_checkpoints_use_case(
    request: CompareCheckpointsRequest
) -> CompareCheckpointsResponse:
    """
    Compare two checkpoints by their forensic fingerprints and component hashes.
    
    Provides detailed comparison showing which components differ.
    
    Args:
        request: CompareCheckpointsRequest containing information about both checkpoints
        
    Returns:
        CompareCheckpointsResponse with detailed comparison results
    """
    try:
        # Generate fingerprints for both checkpoints in parallel to avoid deadlocks
        # Use force_regenerate=False to allow caching, but ensure both are processed consistently
        fingerprint_1_request = FingerprintCheckpointRequest(
            pod_name=request.pod_name_1,
            checkpoint_name=request.checkpoint_name_1,
            force_regenerate=False  # Allow cache for performance
        )
        fingerprint_2_request = FingerprintCheckpointRequest(
            pod_name=request.pod_name_2,
            checkpoint_name=request.checkpoint_name_2,
            force_regenerate=False  # Allow cache for performance
        )
        
        logger.info(f"Generating fingerprints for both checkpoints in parallel: {request.pod_name_1}/{request.checkpoint_name_1} and {request.pod_name_2}/{request.checkpoint_name_2}")
        
        # Run both fingerprint generations in parallel to prevent deadlocks
        result_1, result_2 = await asyncio.gather(
            fingerprint_checkpoint_use_case(fingerprint_1_request),
            fingerprint_checkpoint_use_case(fingerprint_2_request)
        )
        
        logger.info(f"Checkpoint 1 fingerprint: {result_1.fingerprint[:16]}... (components: {len(result_1.forensic_data.get('hashes', {}))})")
        logger.info(f"Checkpoint 2 fingerprint: {result_2.fingerprint[:16]}... (components: {len(result_2.forensic_data.get('hashes', {}))})")
        
        # Compare fingerprints
        are_identical = result_1.fingerprint == result_2.fingerprint
        
        # Compare component hashes
        hashes_1 = result_1.forensic_data.get('hashes', {})
        hashes_2 = result_2.forensic_data.get('hashes', {})
        contents_1 = result_1.forensic_data.get('contents', {})
        contents_2 = result_2.forensic_data.get('contents', {})
        
        component_differences = {}
        component_matches = {}
        all_components = set(list(hashes_1.keys()) + list(hashes_2.keys()))
        
        for component in all_components:
            hash_1 = hashes_1.get(component)
            hash_2 = hashes_2.get(component)
            content_1 = contents_1.get(component)
            content_2 = contents_2.get(component)
            
            # Both None means component missing in both - consider as match
            if hash_1 is None and hash_2 is None:
                component_matches[component] = {
                    "checkpoint_1": None,
                    "checkpoint_2": None,
                    "match": True,
                    "status": "missing_in_both"
                }
            # One is None, other has value - this is a difference
            elif hash_1 is None or hash_2 is None:
                # Assess risk for missing component
                risk_assessment = assess_component_risk(component, {
                    "checkpoint_1": hash_1,
                    "checkpoint_2": hash_2,
                    "status": "missing_in_one"
                })
                
                component_differences[component] = {
                    "checkpoint_1": hash_1,
                    "checkpoint_2": hash_2,
                    "content_1": content_1,  # Include stored content if available
                    "content_2": content_2,  # Include stored content if available
                    "match": False,
                    "status": "missing_in_one" if (hash_1 is None or hash_2 is None) else "present_in_both",
                    "risk_assessment": risk_assessment
                }
            # Both have values - compare them
            elif hash_1 != hash_2:
                # Perform detailed analysis based on component type
                detailed_analysis = None
                try:
                    if component == 'process_tree' and content_1 and content_2:
                        details_1 = extract_process_tree_details(content_1)
                        details_2 = extract_process_tree_details(content_2)
                        # Compare processes
                        pids_1 = {p['pid']: p for p in details_1.get('processes', [])}
                        pids_2 = {p['pid']: p for p in details_2.get('processes', [])}
                        added = [p for pid, p in pids_2.items() if pid not in pids_1]
                        removed = [p for pid, p in pids_1.items() if pid not in pids_2]
                        changed = []
                        for pid in set(pids_1.keys()) & set(pids_2.keys()):
                            p1, p2 = pids_1[pid], pids_2[pid]
                            if p1 != p2:
                                changes = {}
                                if p1.get('ppid') != p2.get('ppid'):
                                    changes['ppid'] = {'old': p1.get('ppid'), 'new': p2.get('ppid')}
                                if p1.get('cmdline') != p2.get('cmdline'):
                                    changes['cmdline'] = {'old': p1.get('cmdline'), 'new': p2.get('cmdline')}
                                if changes:
                                    changed.append({'pid': pid, 'changes': changes})
                        detailed_analysis = {
                            'added_processes': added,
                            'removed_processes': removed,
                            'changed_processes': changed,
                            'process_count_1': details_1.get('process_count', 0),
                            'process_count_2': details_2.get('process_count', 0)
                        }
                    elif component == 'memory_mm' and content_1 and content_2:
                        details_1 = extract_memory_map_details(content_1)
                        details_2 = extract_memory_map_details(content_2)
                        # Compare VMAs
                        vmas_1 = {f"{v.get('start')}-{v.get('end')}": v for v in details_1.get('vmas', [])}
                        vmas_2 = {f"{v.get('start')}-{v.get('end')}": v for v in details_2.get('vmas', [])}
                        new_vmas = [v for key, v in vmas_2.items() if key not in vmas_1]
                        removed_vmas = [v for key, v in vmas_1.items() if key not in vmas_2]
                        changed_vmas = []
                        for key in set(vmas_1.keys()) & set(vmas_2.keys()):
                            v1, v2 = vmas_1[key], vmas_2[key]
                            if v1 != v2:
                                changes = {}
                                if v1.get('prot') != v2.get('prot'):
                                    changes['permissions'] = {'old': v1.get('prot'), 'new': v2.get('prot')}
                                if v1.get('offset') != v2.get('offset'):
                                    changes['offset'] = {'old': v1.get('offset'), 'new': v2.get('offset')}
                                if v1.get('size') != v2.get('size'):
                                    changes['size'] = {'old': v1.get('size'), 'new': v2.get('size')}
                                if changes:
                                    changed_vmas.append({'vma': key, 'changes': changes})
                        detailed_analysis = {
                            'new_vmas': new_vmas,
                            'removed_vmas': removed_vmas,
                            'changed_vmas': changed_vmas,
                            'vma_count_1': details_1.get('vma_count', 0),
                            'vma_count_2': details_2.get('vma_count', 0)
                        }
                    elif component == 'fdinfo' and content_1 and content_2:
                        details_1 = extract_file_descriptor_details(content_1)
                        details_2 = extract_file_descriptor_details(content_2)
                        # Compare file descriptors
                        fds_1 = {fd.get('fd'): fd for fd in details_1.get('file_descriptors', [])}
                        fds_2 = {fd.get('fd'): fd for fd in details_2.get('file_descriptors', [])}
                        new_fds = [fd for fd_id, fd in fds_2.items() if fd_id not in fds_1]
                        closed_fds = [fd for fd_id, fd in fds_1.items() if fd_id not in fds_2]
                        changed_fds = []
                        for fd_id in set(fds_1.keys()) & set(fds_2.keys()):
                            f1, f2 = fds_1[fd_id], fds_2[fd_id]
                            if f1 != f2:
                                changes = {}
                                if f1.get('socket_state') != f2.get('socket_state'):
                                    changes['socket_state'] = {'old': f1.get('socket_state'), 'new': f2.get('socket_state')}
                                if f1.get('file_offset') != f2.get('file_offset'):
                                    changes['file_offset'] = {'old': f1.get('file_offset'), 'new': f2.get('file_offset')}
                                if changes:
                                    changed_fds.append({'fd': fd_id, 'changes': changes})
                        detailed_analysis = {
                            'new_fds': new_fds,
                            'closed_fds': closed_fds,
                            'changed_fds': changed_fds,
                            'fd_count_1': details_1.get('fd_count', 0),
                            'fd_count_2': details_2.get('fd_count', 0)
                        }
                    elif component == 'environment_variables' and content_1 and content_2:
                        env_1 = content_1.get('all_variables', {})
                        env_2 = content_2.get('all_variables', {})
                        added_vars = {k: v for k, v in env_2.items() if k not in env_1}
                        removed_vars = {k: v for k, v in env_1.items() if k not in env_2}
                        changed_vars = {k: {'old': env_1[k], 'new': env_2[k]} 
                                       for k in set(env_1.keys()) & set(env_2.keys()) 
                                       if env_1[k] != env_2[k]}
                        detailed_analysis = {
                            'added_variables': added_vars,
                            'removed_variables': removed_vars,
                            'changed_variables': changed_vars,
                            'variable_count_1': len(env_1),
                            'variable_count_2': len(env_2)
                        }
                except Exception as e:
                    logger.warning(f"Failed to perform detailed analysis for {component}: {str(e)}")
                
                # Assess risk for this component difference
                risk_assessment = assess_component_risk(component, {
                    "checkpoint_1": hash_1,
                    "checkpoint_2": hash_2,
                    "status": "different_values"
                }, detailed_analysis)
                
                component_differences[component] = {
                    "checkpoint_1": hash_1,
                    "checkpoint_2": hash_2,
                    "content_1": content_1,  # Include stored content if available
                    "content_2": content_2,  # Include stored content if available
                    "match": False,
                    "status": "different_values",
                    "detailed_analysis": detailed_analysis,  # Add detailed analysis
                    "risk_assessment": risk_assessment  # Add risk assessment
                }
            # Both have same value - they match
            else:
                component_matches[component] = {
                    "checkpoint_1": hash_1,
                    "checkpoint_2": hash_2,
                    "match": True,
                    "status": "identical"
                }
        
        # Calculate risk summary
        risk_summary = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
            "total_findings": 0,
            "max_risk_score": 0
        }
        
        all_findings = []
        for component, diff in component_differences.items():
            risk_assessment = diff.get("risk_assessment", {})
            if risk_assessment:
                risk_level = risk_assessment.get("risk_level", "info")
                risk_summary[risk_level] = risk_summary.get(risk_level, 0) + 1
                risk_summary["max_risk_score"] = max(
                    risk_summary.get("max_risk_score", 0),
                    risk_assessment.get("risk_score", 0)
                )
                
                findings = risk_assessment.get("findings", [])
                risk_summary["total_findings"] += len(findings)
                for finding in findings:
                    finding["component"] = component
                    all_findings.append(finding)
        
        # Sort findings by severity (critical first)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        all_findings.sort(key=lambda x: (
            severity_order.get(x.get("severity", "info"), 4),
            -x.get("risk_score", 0) if "risk_score" in x else 0
        ))
        
        # Build differences dictionary
        differences = {
            "fingerprints_match": are_identical,
            "size_difference_bytes": abs(result_1.file_size - result_2.file_size),
            "size_1_bytes": result_1.file_size,
            "size_2_bytes": result_2.file_size,
            "component_differences": component_differences,
            "component_matches": component_matches,
            "components_identical": len(component_differences) == 0,
            "components_differing": list(component_differences.keys()),
            "components_matching": list(component_matches.keys()),
            "total_components": len(all_components),
            "matching_count": len(component_matches),
            "differing_count": len(component_differences),
            "risk_summary": risk_summary,
            "findings": all_findings[:50]  # Limit to top 50 findings
        }
        
        message = "Checkpoints are identical" if are_identical else f"Checkpoints differ in {len(component_differences)} component(s)"
        
        return CompareCheckpointsResponse(
            success=True,
            checkpoint_1_fingerprint=result_1.fingerprint,
            checkpoint_2_fingerprint=result_2.fingerprint,
            are_identical=are_identical,
            differences=differences,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error comparing checkpoints: {str(e)}")
        raise Exception(f"Failed to compare checkpoints: {str(e)}")


class VerifyFingerprintRequest(BaseModel):
    """Request model for verifying fingerprint checkpoint"""
    pod_name: str
    checkpoint_name: str


class VerifyFingerprintResponse(BaseModel):
    """Response model for verifying fingerprint checkpoint"""
    success: bool
    fingerprint_matches: bool
    hash_mismatches: Dict[str, Dict[str, Any]]
    content_mismatches: Dict[str, Dict[str, Any]]
    verification_summary: Dict[str, Any]
    message: str


async def verify_fingerprint_checkpoint_use_case(
    request: VerifyFingerprintRequest
) -> VerifyFingerprintResponse:
    """
    Verify the correctness of a fingerprint checkpoint by re-processing the checkpoint
    and comparing with the stored fingerprint JSON.
    
    This function:
    1. Loads the cached fingerprint JSON file
    2. Re-extracts and re-processes the checkpoint (force regeneration)
    3. Compares newly generated hashes with stored hashes
    4. Compares newly generated contents with stored contents
    5. Reports any discrepancies
    
    Args:
        request: VerifyFingerprintRequest containing pod_name and checkpoint_name
        
    Returns:
        VerifyFingerprintResponse with verification results
    """
    extracted_dir = None
    try:
        # Get base directory and checkpoint path
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        checkpoint_dir = os.path.join(BASE_DIR, 'checkpoints', request.pod_name)
        checkpoint_name_clean = request.checkpoint_name.replace('.tar', '')
        checkpoint_file_path = os.path.join(checkpoint_dir, f"{checkpoint_name_clean}.tar")
        fingerprint_file_path = os.path.join(checkpoint_dir, f"{checkpoint_name_clean}_fingerprint.json")
        
        logger.info(f"Verifying fingerprint for checkpoint: {checkpoint_file_path}")
        
        # Check if checkpoint file exists
        if not os.path.exists(checkpoint_file_path):
            raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_file_path}")
        
        # Check if fingerprint file exists
        if not os.path.exists(fingerprint_file_path):
            raise FileNotFoundError(f"Fingerprint file not found: {fingerprint_file_path}. Please generate fingerprint first.")
        
        # Check file size to detect potential corruption
        file_size = os.path.getsize(fingerprint_file_path)
        if file_size == 0:
            raise ValueError(f"Fingerprint file is empty: {fingerprint_file_path}. The file may be corrupted. Please regenerate the fingerprint.")
        
        # Load stored fingerprint with error handling for corrupted JSON
        logger.info(f"Loading stored fingerprint from: {fingerprint_file_path}")
        try:
            with open(fingerprint_file_path, 'r', encoding='utf-8') as f:
                stored_fingerprint_data = json.load(f)
        except json.JSONDecodeError as e:
            error_msg = (
                f"Fingerprint file is corrupted (invalid JSON): {fingerprint_file_path}. "
                f"Error at line {e.lineno}, column {e.colno}: {str(e)}. "
                f"File size: {file_size} bytes. "
                f"Please regenerate the fingerprint by clicking 'Regenerate' in the fingerprint options."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = (
                f"Failed to load fingerprint file: {fingerprint_file_path}. "
                f"Error: {str(e)}. "
                f"Please regenerate the fingerprint by clicking 'Regenerate' in the fingerprint options."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        stored_fingerprint = stored_fingerprint_data.get('fingerprint', '')
        stored_hashes = stored_fingerprint_data.get('hashes', {})
        stored_contents = stored_fingerprint_data.get('contents', {})
        
        logger.info(f"Stored fingerprint: {stored_fingerprint[:16]}...")
        logger.info(f"Stored hashes for {len(stored_hashes)} components")
        
        # Re-generate fingerprint (force regeneration)
        logger.info("Re-processing checkpoint to generate fresh fingerprint...")
        fingerprint_request = FingerprintCheckpointRequest(
            pod_name=request.pod_name,
            checkpoint_name=request.checkpoint_name,
            keep_extracted_folder=False,
            force_regenerate=True  # Force regeneration to verify
        )
        
        new_result = await fingerprint_checkpoint_use_case(fingerprint_request)
        new_fingerprint = new_result.fingerprint
        new_hashes = new_result.forensic_data.get('hashes', {})
        # Convert new contents to JSON-serializable format (bytes -> base64) for comparison
        new_contents = make_json_serializable(new_result.forensic_data.get('contents', {}))
        
        logger.info(f"New fingerprint: {new_fingerprint[:16]}...")
        logger.info(f"New hashes for {len(new_hashes)} components")
        
        # Compare fingerprints
        fingerprint_matches = stored_fingerprint == new_fingerprint
        
        # Compare component hashes
        hash_mismatches = {}
        all_components = set(list(stored_hashes.keys()) + list(new_hashes.keys()))
        
        for component in all_components:
            stored_hash = stored_hashes.get(component)
            new_hash = new_hashes.get(component)
            
            # Both None - match
            if stored_hash is None and new_hash is None:
                continue
            
            # One None, other has value - mismatch
            if stored_hash is None or new_hash is None:
                hash_mismatches[component] = {
                    "stored_hash": stored_hash,
                    "new_hash": new_hash,
                    "status": "missing_in_one",
                    "match": False
                }
            # Both have values - compare
            elif stored_hash != new_hash:
                hash_mismatches[component] = {
                    "stored_hash": stored_hash,
                    "new_hash": new_hash,
                    "status": "hash_mismatch",
                    "match": False
                }
        
        # Compare component contents (if available)
        # Normalize stored contents (may have base64 strings from JSON file, or bytes if corrupted)
        stored_contents_normalized = make_json_serializable(stored_contents)
        
        content_mismatches = {}
        all_content_components = set(list(stored_contents_normalized.keys()) + list(new_contents.keys()))
        
        for component in all_content_components:
            stored_content = stored_contents_normalized.get(component)
            new_content = new_contents.get(component)
            
            # Both None - match
            if stored_content is None and new_content is None:
                continue
            
            # One None, other has value - mismatch
            if stored_content is None or new_content is None:
                content_mismatches[component] = {
                    "stored_content": stored_content,
                    "new_content": new_content,
                    "status": "missing_in_one",
                    "match": False
                }
            else:
                # Both are already normalized (bytes -> base64), so we can compare directly
                # Compare canonicalized JSON
                stored_canonical = canonicalize_json(stored_content)
                new_canonical = canonicalize_json(new_content)
                
                if stored_canonical != new_canonical:
                    content_mismatches[component] = {
                        "stored_content": stored_content,
                        "new_content": new_content,
                        "stored_canonical": stored_canonical,
                        "new_canonical": new_canonical,
                        "status": "content_mismatch",
                        "match": False
                    }
        
        # Build verification summary
        total_components = len(all_components)
        matching_hashes = total_components - len(hash_mismatches)
        matching_contents = len(all_content_components) - len(content_mismatches)
        
        verification_summary = {
            "fingerprint_match": fingerprint_matches,
            "total_components": total_components,
            "matching_hashes": matching_hashes,
            "mismatching_hashes": len(hash_mismatches),
            "matching_contents": matching_contents,
            "mismatching_contents": len(content_mismatches),
            "verification_passed": fingerprint_matches and len(hash_mismatches) == 0 and len(content_mismatches) == 0
        }
        
        # Build message
        if verification_summary["verification_passed"]:
            message = f"Verification passed: Fingerprint and all {total_components} component hashes match."
        else:
            issues = []
            if not fingerprint_matches:
                issues.append("fingerprint mismatch")
            if len(hash_mismatches) > 0:
                issues.append(f"{len(hash_mismatches)} hash mismatch(es)")
            if len(content_mismatches) > 0:
                issues.append(f"{len(content_mismatches)} content mismatch(es)")
            message = f"Verification failed: {', '.join(issues)}"
        
        logger.info(f"Verification complete: {message}")
        
        return VerifyFingerprintResponse(
            success=True,
            fingerprint_matches=fingerprint_matches,
            hash_mismatches=hash_mismatches,
            content_mismatches=content_mismatches,
            verification_summary=verification_summary,
            message=message
        )
        
    except FileNotFoundError as e:
        logger.error(f"File not found during verification: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error verifying fingerprint: {str(e)}")
        raise Exception(f"Failed to verify fingerprint: {str(e)}")
