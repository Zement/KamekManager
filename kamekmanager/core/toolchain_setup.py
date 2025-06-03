# kamekmanager/core/toolchain_setup.py 
import os
import sys
import pathlib
import platform 
import shutil 

from kamekmanager.core import system_utils 
from kamekmanager.common import constants

def _get_actual_devkitpro_windows_path(env_path: str) -> pathlib.Path | None:
    """
    Attempts to resolve the DEVKITPRO path on Windows if it's a POSIX-like path.
    e.g., /opt/devkitpro -> C:\devkitpro (common default)
    Also handles subpaths like /opt/devkitpro/devkitPPC
    """
    if os.name == 'nt':
        original_env_path = env_path # Keep original for messages
        # Normalize to forward slashes for easier parsing
        env_path = env_path.replace("\\", "/")

        if env_path.lower().startswith("/opt/devkitpro"):
            # Determine the base (e.g., C:\devkitPro)
            windows_base = None
            potential_c_path = pathlib.Path("C:\\devkitPro")
            if potential_c_path.is_dir():
                windows_base = potential_c_path
            else:
                for drive_letter in "DEFG": 
                    potential_path = pathlib.Path(f"{drive_letter}:\\devkitPro")
                    if potential_path.is_dir():
                        print(f"Info: DEVKITPRO is set to a /opt/devkitpro style path, but resolved to {potential_path} instead of C:\\devkitPro.")
                        windows_base = potential_path
                        break
            
            if not windows_base:
                print(f"Info: DEVKITPRO environment variable is '{original_env_path}', but standard C:\\devkitPro (or other common drives) not found.", file=sys.stderr)
                return None 

            # Handle subpaths like /opt/devkitpro/devkitPPC
            sub_path = env_path[len("/opt/devkitpro"):].lstrip("/")
            if sub_path:
                return windows_base / sub_path
            return windows_base

        elif env_path.startswith("/"): 
             if len(env_path) > 2 and env_path[2] == '/' and env_path[1].isalpha(): 
                 # e.g. /c/path -> C:\path
                 potential_path = pathlib.Path(f"{env_path[1]}:{env_path[2:]}")
                 # No is_dir() check here, as this function just resolves, caller checks existence
                 return potential_path
             print(f"Info: DEVKITPRO-related env var is a POSIX-like path '{original_env_path}' on Windows. Resolution might be inaccurate if not /opt/devkitpro or /drive/ format.", file=sys.stderr)
             # For other POSIX paths, it's hard to guess.
             # Returning None as resolution is uncertain.
             return None

    # For non-Windows or if it's already a Windows path (or if resolution failed above for some POSIX paths)
    return pathlib.Path(env_path) 


def check_devkitpro_installation() -> dict | None:
    """
    Checks if DevkitPPC (via DEVKITPRO environment variable) is installed and configured.
    Returns: A dictionary with info if found, None otherwise.
    """
    devkitpro_env_val = system_utils.get_environment_variable(constants.DEVKITPRO_ENV_VAR)
    if not devkitpro_env_val:
        print(f"{constants.DEVKITPRO_ENV_VAR} environment variable not set.", file=sys.stderr)
        return None

    actual_devkitpro_path = _get_actual_devkitpro_windows_path(devkitpro_env_val)
    
    if not actual_devkitpro_path or not actual_devkitpro_path.is_dir(): 
        print(f"Resolved DEVKITPRO path '{actual_devkitpro_path}' (from env value '{devkitpro_env_val}') does not exist or is not a directory.", file=sys.stderr)
        return None

    key_tool_name = constants.DEVKITPRO_KEY_TOOL
    if os.name != 'nt' and key_tool_name.endswith(".exe"): 
        key_tool_name = key_tool_name[:-4]
    
    key_tool_path = actual_devkitpro_path / "tools" / "bin" / key_tool_name
    key_tool_found = key_tool_path.is_file()
    if not key_tool_found:
        print(f"Warning: Key tool '{key_tool_name}' not found at expected location: {key_tool_path}", file=sys.stderr)

    devkitppc_dir_name = "devkitPPC" 
    devkitppc_path_expected = actual_devkitpro_path / devkitppc_dir_name
    if not devkitppc_path_expected.is_dir():
        print(f"Warning: Expected devkitPPC directory not found at: {devkitppc_path_expected}", file=sys.stderr)

    # Check if the msys2/usr/bin (which contains compilers) is in PATH
    msys2_bin_path = actual_devkitpro_path / "msys2" / "usr" / "bin"
    msys2_bin_in_path = False
    system_path_var = os.getenv("PATH", "")
    if system_path_var:
        # Normalize paths for comparison
        normalized_msys2_bin_path = str(msys2_bin_path.resolve()).lower()
        for path_entry in system_path_var.split(os.pathsep):
            if str(pathlib.Path(path_entry).resolve()).lower() == normalized_msys2_bin_path:
                msys2_bin_in_path = True
                break
    
    # Check DEVKITPPC environment variable consistency
    devkitppc_env_val = system_utils.get_environment_variable("DEVKITPPC")
    if not devkitppc_env_val:
        print("Warning: DEVKITPPC environment variable is not set.", file=sys.stderr)
    else:
        resolved_devkitppc_env_path = _get_actual_devkitpro_windows_path(devkitppc_env_val)
        if not resolved_devkitppc_env_path or not resolved_devkitppc_env_path.is_dir() or \
           resolved_devkitppc_env_path.resolve() != devkitppc_path_expected.resolve():
             print(f"Warning: DEVKITPPC env var ('{devkitppc_env_val}') resolved to ('{resolved_devkitppc_env_path}') does not match expected devkitPPC path ('{devkitppc_path_expected}').", file=sys.stderr)

    return {
        "DEVKITPRO_ENV": devkitpro_env_val,
        "resolved_path": str(actual_devkitpro_path), 
        "key_tool_found": key_tool_found,
        "msys2_bin_in_path": msys2_bin_in_path # Changed from gcc_in_path
    }


def install_devkitpro_interactive(download_dir: pathlib.Path) -> bool:
    """
    Guides the user through downloading and installing/updating DevkitPPC.
    """
    print("DevkitPro (which includes DevkitPPC) is typically installed using an installer or updater.")
    
    platform_system = platform.system().lower()
    installer_url = constants.DEVKITPRO_UPDATER_URL 
    
    print(f"The primary method is often the DevkitPro Updater (.jar): {installer_url}")
    print("Alternatively, check https://devkitpro.org/wiki/Getting_Started for platform-specific graphical installers.")


    installer_name = installer_url.split('/')[-1] 
    installer_path = download_dir / installer_name

    if not system_utils.download_file(installer_url, installer_path):
        print(f"Failed to download DevkitPro Updater from {installer_url}", file=sys.stderr)
        return False

    print(f"DevkitPro Updater downloaded to: {installer_path}")

    if installer_path.suffix == '.exe':
        
        run_command_parts = [str(installer_path)]
        print(f"\nAttempting to launch DevkitPro Updater with command: {' '.join(run_command_parts)}")
        print("This is an interactive updater. Please follow the instructions in its window/console output.")
        
        system_utils.run_command(run_command_parts, display_output_live=True, check_return_code=False, capture_output=False)
        print("DevkitPro Updater process finished or launched. After it completes, you might need to restart your terminal.")

    else:
        print(f"\nDownloaded DevkitPro tool: {installer_path}")
        print("Please run it manually according to the instructions for your operating system.")

    print("\nAfter DevkitPro installation/update, ensure DEVKITPRO environment variable is set")
    print(f"and the DevkitPro MSYS2 bin directory (e.g., C:\\devkitPro\\msys2\\usr\\bin on Windows) is in your system PATH.")
    print("You may need to restart your terminal or PC for these changes to take effect.")
    return True

# --- Placeholders for CodeWarrior ---
def check_codewarrior_installation() -> bool:
    print("Placeholder: check_codewarrior_installation() called.")
    return False

def install_codewarrior_interactive(download_dir: pathlib.Path) -> bool:
    print("Placeholder: install_codewarrior_interactive() called.")
    return False