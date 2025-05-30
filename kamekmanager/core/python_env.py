# kamekmanager/core/python_env.py
import sys
import subprocess
import importlib.util
import pathlib 
import os 
import re 
import tempfile 
import shutil 

from kamekmanager.core import system_utils 
from kamekmanager.common import constants

# Moved requests import to the top as it's essential for the primary method
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# BS4 is no longer used in the primary path for get_latest_python_download_url
# try:
#     from bs4 import BeautifulSoup
#     BS4_AVAILABLE = True
# except ImportError:
#     BS4_AVAILABLE = False 

def get_python_executable_info(python_exe_path_str: str) -> dict | None:
    """Gets version and path for a given Python executable."""
    if not python_exe_path_str: 
        return None
    python_exe = pathlib.Path(python_exe_path_str)
    if not python_exe.is_file():
        return None

    try:
        result = system_utils.run_command([str(python_exe), "--version"], capture_output=True, check_return_code=False)
        if result and result.returncode == 0:
            output = result.stdout.strip() + result.stderr.strip() 
            match = re.search(r"Python (\d+\.\d+\.\d+)", output, re.IGNORECASE)
            if match:
                version_str = match.group(1)
                version_tuple = tuple(map(int, version_str.split('.')))
                is_windows_store_app = False
                if os.name == 'nt':
                    try:
                        resolved_path = python_exe.resolve()
                        if "windowsapps" in str(resolved_path).lower():
                            is_windows_store_app = True
                    except Exception: 
                        pass
                return {
                    "executable": str(python_exe.resolve()),
                    "version_str": version_str,
                    "version_tuple": version_tuple,
                    "is_windows_store_app": is_windows_store_app
                }
        return None
    except Exception as e:
        print(f"Error getting info for Python executable {python_exe}: {e}", file=sys.stderr)
        return None

def check_python_installation(min_version: tuple = constants.MIN_PYTHON_VERSION, specific_exe: str | None = None) -> dict | None:
    python_to_check = specific_exe if specific_exe else sys.executable
    if not python_to_check:
        print("No Python executable specified or found (sys.executable is empty).", file=sys.stderr)
        return None
    info = get_python_executable_info(python_to_check)
    if not info:
        return None
    if info["version_tuple"][0] == 2:
        print(f"Warning: Python at {info['executable']} is Python 2 ({info['version_str']}). This tool requires Python 3.", file=sys.stderr)
        return None 
    if info["version_tuple"] < min_version:
        print(f"Python version {info['version_str']} at {info['executable']} is older than required {min_version[0]}.{min_version[1]}+.", file=sys.stderr)
        return None
    if info["is_windows_store_app"]:
        print(f"Warning: Python at {info['executable']} appears to be a Microsoft Store version.", file=sys.stderr)
        print("MS Store Python has limitations and may not work correctly with all development tools.")
        print("It's recommended to uninstall it and install Python from python.org.")
    
    python_in_path = shutil.which("python")
    if not specific_exe and python_in_path and (pathlib.Path(sys.executable).resolve() != pathlib.Path(python_in_path).resolve()):
        python_cmd_info = get_python_executable_info(python_in_path)
        if python_cmd_info and python_cmd_info["version_tuple"][0] == 2:
            print(f"Warning: The 'python' command in your PATH points to Python 2 ({python_cmd_info['version_str']} at {python_cmd_info['executable']}).", file=sys.stderr)
            print("Ensure you use 'python3' or the direct path to your Python 3 interpreter for Python 3 tasks.", file=sys.stderr)
    return info

def _get_latest_python_version_from_api() -> str | None:
    """Helper to get the latest stable Python version string from endoflife.date API."""
    if not REQUESTS_AVAILABLE:
        print("Library 'requests' is required to fetch latest Python version from API.", file=sys.stderr)
        print("Please install it: pip install requests")
        return None
    try:
        api_url = "[https://endoflife.date/api/python.json](https://endoflife.date/api/python.json)" # Corrected URL
        print(f"Fetching latest Python version info from: {api_url}")
        headers = {'User-Agent': f'{constants.APP_NAME}/{constants.APP_VERSION}'}
        response = requests.get(api_url, timeout=10, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if data and isinstance(data, list) and len(data) > 0:
            latest_cycle_info = None
            # Iterate to find the newest cycle that is not EOL (eol: false)
            # or the absolute newest if all are EOL (though unlikely for Python's main entry)
            for cycle_info in data: # API sorts by release date, newest first
                if isinstance(cycle_info.get("eol"), bool) and cycle_info["eol"] is False:
                    latest_cycle_info = cycle_info
                    break
                # If no cycle has "eol: false", we might take the first one as the most recent.
                # However, the API should ideally always have a current non-EOL for Python.
                # If we only find EOL cycles, it's safer to indicate an issue or use a fallback.
            
            if not latest_cycle_info and data: # Fallback to the very first entry if no "eol: false" found
                print("Warning: Could not find a definitively non-EOL Python cycle from API, using the newest listed.", file=sys.stderr)
                latest_cycle_info = data[0]


            if latest_cycle_info and "latest" in latest_cycle_info:
                latest_version_str = latest_cycle_info["latest"]
                print(f"Latest stable Python version from API: {latest_version_str}")
                return latest_version_str
        print("Could not parse latest Python version from API response structure.", file=sys.stderr)
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching latest Python version from API ({api_url}): {e}", file=sys.stderr)
        return None
    except Exception as e: 
        print(f"Unexpected error processing API response for Python version: {e}", file=sys.stderr)
        return None

def get_latest_python_download_url(os_filter="win64", version_str_override: str | None = None) -> str | None:
    """
    Attempts to find the download URL for the latest (or specified) stable Python installer.
    Uses endoflife.date API for version, then constructs FTP URL.
    Args:
        os_filter: "win64", "win32", "macos".
        version_str_override: If provided, uses this version string instead of fetching the latest.
    Returns:
        The direct download URL string or None if not found.
    """
    latest_version_str = version_str_override if version_str_override else _get_latest_python_version_from_api()

    if latest_version_str:
        base_ftp_url = constants.PYTHON_FTP_BASE_URL # Corrected URL
        filename = ""
        if os_filter == "win64":
            filename = f"python-{latest_version_str}-amd64.exe"
        elif os_filter == "win32":
            # For 3.9+, 32-bit is just .exe, for <3.9 it was python-X.Y.Z.msi or .exe
            # Let's assume .exe for simplicity, may need refinement for older versions if targeted
            filename = f"python-{latest_version_str}.exe" 
        elif os_filter == "macos":
            # Example: python-3.12.3-macos11.pkg
            # The "macosXX" part can vary. For very new versions, it's often macos11.
            # This is a best guess.
            v_tuple = tuple(map(int, latest_version_str.split('.')))
            macos_ver_suffix = "macos11" # Default for newer Pythons
            if v_tuple < (3, 9): # Older Pythons might use macos10.9
                macos_ver_suffix = "macos10.9"
            filename = f"python-{latest_version_str}-{macos_ver_suffix}.pkg"
        else:
            print(f"Unsupported OS filter for direct FTP URL: {os_filter}", file=sys.stderr)
            return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK

        if filename:
            direct_url = f"{base_ftp_url}/{latest_version_str}/{filename}"
            print(f"Constructed download URL: {direct_url}")
            # Optional: Add a HEAD request here to check if the URL actually exists
            # if REQUESTS_AVAILABLE:
            #     try:
            #         head_resp = requests.head(direct_url, timeout=5)
            #         if head_resp.status_code == 200:
            #             return direct_url
            #         else:
            #             print(f"Warning: Constructed URL {direct_url} returned status {head_resp.status_code}", file=sys.stderr)
            #             return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK # Fallback if constructed URL is bad
            #     except requests.exceptions.RequestException:
            #         print(f"Warning: Could not verify constructed URL {direct_url}", file=sys.stderr)
            #         return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK # Fallback
            return direct_url # Return constructed URL directly for now

    print("Could not determine Python version for download URL construction.", file=sys.stderr)
    return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK


def install_python_interactive(version_or_url: str, download_dir: pathlib.Path) -> bool:
    installer_url = None
    if version_or_url.lower() == "latest":
        print("Attempting to find the latest Python installer URL...")
        installer_url = get_latest_python_download_url() # Defaults to win64
    elif version_or_url.startswith("http://") or version_or_url.startswith("https://"):
        installer_url = version_or_url
    else: 
        # Assume version_or_url is a version string like "3.10.5"
        print(f"Attempting to find installer URL for Python version: {version_or_url}")
        installer_url = get_latest_python_download_url(version_str_override=version_or_url)

    if not installer_url:
        print("Could not determine Python installer URL.", file=sys.stderr)
        return False

    installer_name = installer_url.split('/')[-1]
    # Ensure a reasonable default filename if the URL is weird
    if not (installer_name.endswith((".exe", ".pkg", ".dmg")) or "python_installer_downloaded" in installer_name):
        print(f"Warning: Download URL does not appear to point to a standard installer file: {installer_name}", file=sys.stderr)
        original_extension = pathlib.Path(installer_name).suffix
        safe_version_or_url = re.sub(r'[^\w\.-]', '_', version_or_url) # Sanitize for filename
        installer_name = f"python_installer_{safe_version_or_url}{original_extension if original_extension else '.exe'}"
        print(f"Using generic filename: {installer_name}")

    installer_path = download_dir / installer_name

    if not system_utils.download_file(installer_url, installer_path):
        print(f"Failed to download Python installer from {installer_url}", file=sys.stderr)
        return False

    print(f"Python installer downloaded to: {installer_path}")
    print("Please run the installer manually.")
    print("IMPORTANT: During installation, ensure you check options like:")
    print("  - 'Add Python X.Y to PATH'")
    print("  - 'Install for all users' (if desired, requires admin for installer too)")
    print("  - Consider customizing the installation path if needed.")

    if os.name == 'nt':
        try:
            print(f"Attempting to launch installer: {installer_path}...")
            os.startfile(installer_path) # This is for Windows
            print("Installer launched. Please follow its instructions.")
        except Exception as e:
            print(f"Could not automatically launch the installer: {e}", file=sys.stderr)
            print(f"Please navigate to '{installer_path.parent}' and run '{installer_path.name}' manually.")
    elif os.name == 'posix': # macOS
        # For .pkg files on macOS, `open` command can be used
        if installer_path.suffix == '.pkg':
            print(f"Attempting to open installer with default application: {installer_path}")
            system_utils.run_command(['open', str(installer_path)], check_return_code=False)
        else:
            print(f"Please run the downloaded installer from: {installer_path}")
    else:
        print(f"Please run the downloaded installer from: {installer_path}")
    
    print("\nAfter installation, you might need to restart your terminal or KamekManager.")
    return True

def update_pip(python_exe_path_str: str) -> bool:
    python_info = get_python_executable_info(python_exe_path_str)
    if not python_info:
        print(f"Cannot update pip: Invalid Python executable path {python_exe_path_str}", file=sys.stderr)
        return False
    
    print(f"Attempting to upgrade pip for Python at {python_info['executable']}...")
    pip_upgrade_cmd = [python_info['executable'], "-m", "pip", "install", "--upgrade", "pip"]
    result = system_utils.run_command(pip_upgrade_cmd, display_output_live=True, check_return_code=False)
    
    if result and result.returncode == 0:
        print("pip upgraded successfully.")
        return True
    else:
        print("Failed to upgrade pip.", file=sys.stderr)
        stderr_output = ((result.stdout or "") + (result.stderr or "")).lower() 
        if result and result.returncode !=0 and ("permission denied" in stderr_output or "environmenterror" in stderr_output or "access is denied" in stderr_output):
             print("Attempting pip upgrade with --user flag due to potential permission issues...")
             pip_upgrade_cmd_user = [python_info['executable'], "-m", "pip", "install", "--upgrade", "pip", "--user"]
             result_user = system_utils.run_command(pip_upgrade_cmd_user, display_output_live=True, check_return_code=True)
             if result_user and result_user.returncode == 0:
                  print("pip upgraded successfully with --user flag.")
                  return True
             else:
                  print("Failed to upgrade pip even with --user flag.", file=sys.stderr)
        return False

def check_and_install_pip_packages(python_exe_path_str: str, packages: list[str]) -> bool:
    python_info = get_python_executable_info(python_exe_path_str)
    if not python_info:
        print(f"Cannot manage pip packages: Invalid Python executable path {python_exe_path_str}", file=sys.stderr)
        return False
    python_exe = python_info['executable']
    if not packages:
        print(f"No pip packages specified to check or install for {python_exe}.")
        return True

    all_successful = True
    print(f"Managing pip packages for Python at: {python_exe}")
    for package_spec in packages:
        package_name = package_spec.split('==')[0].split('>=')[0].split('<=')[0].split('!=')[0].split('~=')[0]
        pip_show_cmd = [python_exe, "-m", "pip", "show", package_name]
        result = system_utils.run_command(pip_show_cmd, capture_output=True, check_return_code=False)
        if result and result.returncode == 0:
            print(f"Package '{package_name}' (from spec '{package_spec}') is already installed for {python_exe}.")
        else:
            print(f"Package '{package_name}' (from spec '{package_spec}') not found for {python_exe}. Attempting to install...")
            pip_install_cmd = [python_exe, "-m", "pip", "install", package_spec]
            install_result = system_utils.run_command(pip_install_cmd, display_output_live=True, check_return_code=True)
            if install_result and install_result.returncode == 0:
                print(f"Successfully installed '{package_spec}' for {python_exe}.")
            else:
                print(f"Failed to install '{package_spec}' for {python_exe}.", file=sys.stderr)
                all_successful = False
    return all_successful

def upgrade_python_interactive(old_python_exe_str: str, download_dir: pathlib.Path) -> bool:
    print(f"--- Starting Python Upgrade Process for {old_python_exe_str} ---")
    old_python_info = check_python_installation(min_version=(0,0), specific_exe=old_python_exe_str) 
    if not old_python_info:
        print(f"Could not get information for the old Python at '{old_python_exe_str}'. Aborting upgrade.", file=sys.stderr)
        return False
    old_python_exe = old_python_info['executable']
    print(f"Old Python version: {old_python_info['version_str']} at {old_python_exe}")
    if old_python_info['is_windows_store_app']:
        print("The old Python is a Microsoft Store version. Upgrading this type directly is not recommended.")
        print("Consider uninstalling it via Windows Settings and then installing a fresh version from python.org using KamekManager's --install-python.")
        if not system_utils.prompt_user_for_confirmation("Do you want to proceed with attempting an upgrade guide anyway (not recommended)?"):
            return False
    print("\nStep 1: Backing up list of installed packages from the old Python...")
    requirements_content = None
    pip_freeze_cmd = [old_python_exe, "-m", "pip", "freeze"]
    freeze_result = system_utils.run_command(pip_freeze_cmd, capture_output=True, check_return_code=False)
    if freeze_result and freeze_result.returncode == 0 and freeze_result.stdout:
        requirements_content = freeze_result.stdout
        print("Successfully retrieved package list from old Python.")
    else:
        print("Warning: Could not retrieve package list from the old Python.", file=sys.stderr)
        if not system_utils.prompt_user_for_confirmation("Continue with Python upgrade without package migration?"):
            return False
    print("\nStep 2: Installing a new version of Python...")
    print("It is strongly recommended to install the new Python version to a DIFFERENT directory.")
    if not install_python_interactive("latest", download_dir): 
        print("Failed to initiate new Python installation. Aborting upgrade.", file=sys.stderr)
        return False
    print("\n--- IMPORTANT ---")
    print("After the new Python installer finishes, please provide the path to the new python.exe")
    new_python_exe_str = ""
    while True:
        new_python_exe_str = input("Enter the full path to the new python.exe: ").strip().replace("\"", "") 
        if not new_python_exe_str:
            if system_utils.prompt_user_for_confirmation("Skip package reinstallation for now?"):
                requirements_content = None 
                break
            else: continue
        new_python_info_temp = get_python_executable_info(new_python_exe_str)
        if new_python_info_temp:
            if pathlib.Path(new_python_info_temp['executable']).resolve() == pathlib.Path(old_python_exe).resolve():
                print("Error: The new Python path cannot be the same as the old Python path.", file=sys.stderr)
                continue
            print(f"New Python identified: {new_python_info_temp['version_str']} at {new_python_info_temp['executable']}")
            if not system_utils.prompt_user_for_confirmation(f"Is this correct?"):
                continue
            break
        else:
            print(f"Path '{new_python_exe_str}' does not seem to be a valid Python executable. Please try again.")
    if not new_python_exe_str and not requirements_content:
        print("Python upgrade process finished (new Python installed, package migration skipped).")
        return True
    if not new_python_exe_str and requirements_content:
        print("New Python path not provided. Cannot reinstall packages.", file=sys.stderr)
        print(f"Your old package list was:\n{requirements_content}")
        return False 
    
    new_python_exe_info = get_python_executable_info(new_python_exe_str)
    if not new_python_exe_info: # Should not happen if loop above worked, but defensive check
        print(f"Critical error: Could not re-verify new Python path {new_python_exe_str}", file=sys.stderr)
        return False
    new_python_exe = new_python_exe_info['executable']

    print(f"\nStep 3: Updating pip for the new Python at {new_python_exe}...")
    if not update_pip(new_python_exe):
        print("Warning: Failed to update pip for the new Python.", file=sys.stderr)
        if not system_utils.prompt_user_for_confirmation("Continue with package reinstallation?"):
            return False 
    if requirements_content:
        print(f"\nStep 4: Reinstalling packages into the new Python at {new_python_exe}...")
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding='utf-8') as tmp_req_file:
            tmp_req_file.write(requirements_content)
            tmp_req_file_path_str = tmp_req_file.name
        print(f"Using temporary requirements file: {tmp_req_file_path_str}")
        pip_install_cmd = [new_python_exe, "-m", "pip", "install", "--no-cache-dir", "-r", tmp_req_file_path_str]
        install_result = system_utils.run_command(pip_install_cmd, display_output_live=True, check_return_code=False) 
        if install_result and install_result.returncode == 0:
            print("Successfully reinstalled packages into the new Python.")
        else:
            print("Warning: Some packages may not have been reinstalled correctly.", file=sys.stderr)
            print(f"You can try again manually: \"{new_python_exe}\" -m pip install -r \"{tmp_req_file_path_str}\"")
            print(f"The requirements file is saved at: {tmp_req_file_path_str}")
        try:
            pathlib.Path(tmp_req_file_path_str).unlink(missing_ok=True)
        except Exception as e_del:
            print(f"Note: Could not delete temporary requirements file {tmp_req_file_path_str}: {e_del}", file=sys.stderr)
    print("\n--- Python Upgrade Process Summary ---")
    print(f"Old Python: {old_python_exe} (Version: {old_python_info['version_str']})")
    if new_python_exe_str and new_python_exe_info: # Check new_python_exe_info as well
         print(f"New Python: {new_python_exe_info['executable']} (Version: {new_python_exe_info['version_str']})")
    else:
        print("New Python installation was guided, but path not confirmed for package migration.")
    if requirements_content: print("Attempted to migrate packages.")
    else: print("Package migration was skipped or failed at backup stage.")
    print("\nRecommendation: You can now uninstall the old Python version if you are satisfied with the new setup.")
    print(f"Path to old Python: {old_python_exe}")
    return True

def ensure_python_in_path(python_exe_path: pathlib.Path | None = None) -> bool:
    print(f"Placeholder: ensure_python_in_path({python_exe_path}) called.", file=sys.stderr)
    print("Please ensure Python's Scripts directory and main directory are in your PATH.", file=sys.stderr)
    print("This is usually handled by the Python installer if you check 'Add Python to PATH'.")
    return False 