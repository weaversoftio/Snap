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
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
from flows.proccess_utils import run

logger = logging.getLogger("automation_api")


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
    
    Returns:
        True if crit is available, False otherwise
    """
    try:
        cmd = ['which', 'crit']
        result = await run(cmd, check=False, capture_output=True, text=True)
        return result.returncode == 0 and result.stdout.strip() != ''
    except Exception:
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
            
        cmd = ['crit', 'decode', '-i', str(img_path)]
        result = await run(cmd, check=False, capture_output=True, text=True)
        
        if result.returncode != 0:
            # Check if it's a "command not found" error
            if 'No such file or directory' in str(result.stderr) or 'command not found' in str(result.stderr).lower():
                logger.warning(f"crit command not found. Please install crit (part of CRIU tools) to decode CRIU images.")
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
                # Retry the decode
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


async def hash_criu_image(img_path: Path, component_name: str) -> Optional[str]:
    """
    Decode and hash a CRIU image file.
    
    If crit is not available, falls back to hashing the raw file content.
    
    Args:
        img_path: Path to the .img file
        component_name: Name of the component for logging
        
    Returns:
        SHA256 hash of canonicalized decoded JSON, or raw file hash if crit unavailable
    """
    decoded = await decode_criu_image(img_path)
    if decoded is None:
        # Fallback: hash the raw file if crit is not available
        crit_available = await check_crit_available()
        if not crit_available and img_path.exists():
            logger.info(f"crit not available, using raw file hash for {component_name}: {img_path.name}")
            try:
                return hash_file(img_path)
            except Exception as e:
                logger.warning(f"Failed to hash raw file {img_path}: {str(e)}")
                return None
        return None
    
    canonical = canonicalize_json(decoded)
    return hash_string(canonical)


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
                        img_hash = await hash_criu_image(match, component_name)
                        if img_hash:
                            component_hashes.append(f"{match.name}:{img_hash}")
                            logger.info(f"Successfully hashed {component_name}: {match.name} -> {img_hash[:16]}...")
                            # Also decode and store content if requested
                            if include_contents and contents is not None:
                                decoded = await decode_criu_image(match)
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
                        img_hash = await hash_criu_image(img_path, component_name)
                        if img_hash:
                            hashes[component_name] = img_hash
                            # Also decode and store content if requested
                            if include_contents and contents is not None:
                                decoded = await decode_criu_image(img_path)
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
    
    # Return both hashes and contents
    result = {"hashes": hashes}
    if include_contents and contents is not None:
        result["contents"] = contents
    return result


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
        # Log tar file contents for debugging
        with tarfile.open(tar_path, 'r:*') as tar:
            members = tar.getmembers()
            logger.info(f"Tar file contains {len(members)} members")
            # Log first 20 members
            for i, member in enumerate(members[:20]):
                logger.debug(f"  {i+1}. {member.name} (size: {member.size}, type: {member.type})")
            if len(members) > 20:
                logger.debug(f"  ... and {len(members) - 20} more")
            
            tar.extractall(path=temp_dir)
        
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
        
        # Fix permissions for the entire extracted directory
        try:
            fix_permissions(temp_dir)
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
                if content_1 is not None:
                    logger.info(f"Loaded {component_name} content from fingerprint file for checkpoint 1")
        except Exception as e:
            logger.warning(f"Failed to load content from fingerprint file 1: {str(e)}")
    
    if fingerprint_file_2.exists():
        try:
            with open(fingerprint_file_2, 'r') as f:
                fingerprint_data_2 = json.load(f)
                contents_2 = fingerprint_data_2.get('contents', {})
                content_2 = contents_2.get(component_name)
                if content_2 is not None:
                    logger.info(f"Loaded {component_name} content from fingerprint file for checkpoint 2")
        except Exception as e:
            logger.warning(f"Failed to load content from fingerprint file 2: {str(e)}")
    
    # If we have both contents from fingerprint files, use them directly
    if content_1 is not None and content_2 is not None:
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
            "has_content_1": content_1 is not None,
            "has_content_2": content_2 is not None,
            "source": "fingerprint_cache"  # Indicate we used cached content
        }
    
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
        else:
            checkpoint_dir_2 = checkpoint_file_2
            parent_dir_2 = checkpoint_dir_2.parent
        
        # Get component content from both (only if not already loaded from fingerprint)
        logger.info(f"Getting content for component: {component_name}")
        if content_1 is None:
            content_1 = await get_component_content(checkpoint_dir_1, parent_dir_1, component_name)
        if content_2 is None:
            content_2 = await get_component_content(checkpoint_dir_2, parent_dir_2, component_name)
        
        logger.info(f"Content 1 found: {content_1 is not None}")
        logger.info(f"Content 2 found: {content_2 is not None}")
        
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
            "has_content_1": content_1 is not None,
            "has_content_2": content_2 is not None
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
                with open(fingerprint_file_path, 'r') as f:
                    cached_data = json.load(f)
                
                # Verify the cached fingerprint is for the same checkpoint file
                if cached_data.get('checkpoint_dir') == checkpoint_file_path:
                    cached_fingerprint = cached_data
                    logger.info("Using cached fingerprint")
                else:
                    logger.info("Cached fingerprint is for a different checkpoint file, regenerating...")
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
        try:
            with open(fingerprint_file_path, 'w') as f:
                json.dump(forensic_data, f, indent=2)
            logger.info(f"Forensic fingerprint saved to cache: {fingerprint_file_path}")
        except Exception as e:
            logger.warning(f"Failed to save fingerprint file: {str(e)}")
        
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
        # Generate fingerprints for both checkpoints
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
        
        logger.info(f"Generating fingerprint for checkpoint 1: {request.pod_name_1}/{request.checkpoint_name_1}")
        result_1 = await fingerprint_checkpoint_use_case(fingerprint_1_request)
        logger.info(f"Checkpoint 1 fingerprint: {result_1.fingerprint[:16]}... (components: {len(result_1.forensic_data.get('hashes', {}))})")
        
        logger.info(f"Generating fingerprint for checkpoint 2: {request.pod_name_2}/{request.checkpoint_name_2}")
        result_2 = await fingerprint_checkpoint_use_case(fingerprint_2_request)
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
                component_differences[component] = {
                    "checkpoint_1": hash_1,
                    "checkpoint_2": hash_2,
                    "content_1": content_1,  # Include stored content if available
                    "content_2": content_2,  # Include stored content if available
                    "match": False,
                    "status": "missing_in_one" if (hash_1 is None or hash_2 is None) else "present_in_both"
                }
            # Both have values - compare them
            elif hash_1 != hash_2:
                component_differences[component] = {
                    "checkpoint_1": hash_1,
                    "checkpoint_2": hash_2,
                    "content_1": content_1,  # Include stored content if available
                    "content_2": content_2,  # Include stored content if available
                    "match": False,
                    "status": "different_values"
                }
            # Both have same value - they match
            else:
                component_matches[component] = {
                    "checkpoint_1": hash_1,
                    "checkpoint_2": hash_2,
                    "match": True,
                    "status": "identical"
                }
        
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
            "differing_count": len(component_differences)
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
