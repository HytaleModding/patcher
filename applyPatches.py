import subprocess
import os
import glob

from loguru import logger as log

DECOMPILE_DIR = "work/decompile/"
PATCHES_DIR = "patches/"


def apply_patch(patch_file: str) -> bool:
    """Apply a single patch file using git apply"""
    try:
        patch_path = os.path.abspath(patch_file)
        
        result = subprocess.run(
            ["git", "apply", patch_path],
            cwd=DECOMPILE_DIR,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            log.info(f"Successfully applied patch: {patch_file}")
            return True
        else:
            log.error(f"Failed to apply patch {patch_file}: {result.stderr}")
            return False
            
    except Exception as e:
        log.error(f"Error applying patch {patch_file}: {e}")
        return False

def find_patch_files() -> list[str]:
    """Find all .patch files in the patches directory"""
    patch_pattern = os.path.join(PATCHES_DIR, "**", "*.patch")
    patch_files = glob.glob(patch_pattern, recursive=True)
    return sorted(patch_files)

def main():
    if not os.path.exists(DECOMPILE_DIR):
        log.error(f"Decompile directory {DECOMPILE_DIR} does not exist")
        return
    
    if not os.path.exists(os.path.join(DECOMPILE_DIR, ".git")):
        log.error(f"Decompile directory {DECOMPILE_DIR} is not a git repository")
        return
    
    if not os.path.exists(PATCHES_DIR):
        log.info(f"Patches directory {PATCHES_DIR} does not exist. Nothing to apply.")
        return
    
    patch_files = find_patch_files()
    
    if not patch_files:
        log.info("No patch files found. Nothing to apply.")
        return
    
    log.info(f"Found {len(patch_files)} patch file(s)")
    
    applied_count = 0
    failed_count = 0
    
    for patch_file in patch_files:
        if apply_patch(patch_file):
            applied_count += 1
        else:
            failed_count += 1
    
    log.info(f"Patch application complete. Applied: {applied_count}, Failed: {failed_count}")
    
    if failed_count > 0:
        log.warning("Some patches failed to apply. Check the logs above for details.")

if __name__ == "__main__":
    main()