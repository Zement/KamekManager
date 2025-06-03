# kamekmanager/core/python_env.py
import sys
import subprocess
import importlib.util
import pathlib 
import os 
import re 
import tempfile 
import shutil 
from datetime import datetime 

from kamekmanager.core import system_utils 
from kamekmanager.common import constants

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

def get_python_executable_info(python_exe_path_str: str) -> dict | None:
    """Gets version and path for a given Python executable."""
    if not python_exe_path_str: 
        return None
    python_exe = pathlib.Path(python_exe_path_str)
    if not python_exe.is_file(): 
        resolved_by_which = shutil.which(str(python_exe))
        if resolved_by_which:
            python_exe = pathlib.Path(resolved_by_which)
        else:
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
                        actual_path = python_exe.resolve()
                        if "windowsapps" in str(actual_path).lower():
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
        python_in_path = shutil.which("python3") or shutil.which("python")
        if not python_in_path:
            print("No Python executable specified or found (sys.executable is empty and none in PATH).", file=sys.stderr)
            return None
        python_to_check = python_in_path
        print(f"Checking Python found in PATH: {python_to_check}")

    info = get_python_executable_info(python_to_check)
    if not info:
        print(f"Could not get valid information for Python at '{python_to_check}'.", file=sys.stderr)
        return None

    if info["version_tuple"][0] == 2:
        print(f"Warning: Python at {info['executable']} is Python 2 ({info['version_str']}). This tool requires Python 3.", file=sys.stderr)
        return None 
    if info["version_tuple"] < min_version:
        print(f"Python version {info['version_str']} at {info['executable']} is older than required {min_version[0]}.{min_version[1]}+.", file=sys.stderr)
        return None
    if info["is_windows_store_app"]:
        print(f"Warning: Python at {info['executable']} appears to be a Microsoft Store version.")
        print("MS Store Python has limitations and may not work correctly with all development tools.")
        print("It's recommended to uninstall it and install Python from python.org.")
    
    if not specific_exe: 
        python_cmd_in_path = shutil.which("python")
        if python_cmd_in_path:
            current_interpreter_resolved_path = pathlib.Path(sys.executable).resolve()
            python_cmd_resolved_path = pathlib.Path(python_cmd_in_path).resolve()

            if current_interpreter_resolved_path != python_cmd_resolved_path:
                python_cmd_info = get_python_executable_info(python_cmd_in_path)
                if python_cmd_info and python_cmd_info["version_tuple"][0] == 2:
                    print(f"Warning: The 'python' command in your PATH points to Python 2 ({python_cmd_info['version_str']} at {python_cmd_info['executable']}).", file=sys.stderr)
    return info

def _get_latest_python_version_from_api() -> str | None:
    """Helper to get the latest stable Python version string from endoflife.date API."""
    if not REQUESTS_AVAILABLE:
        print("Library 'requests' is required to fetch latest Python version from API.", file=sys.stderr)
        print("Please install it: pip install requests")
        return None
    try:
        api_url = "https://endoflife.date/api/python.json" 
        print(f"Fetching latest Python version info from: {api_url}")
        headers = {'User-Agent': f'{constants.APP_NAME}/{constants.APP_VERSION}'}
        response = requests.get(api_url, timeout=10, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if data and isinstance(data, list) and len(data) > 0:
            latest_cycle_info = None
            for cycle_info in data: 
                eol_status = cycle_info.get("eol")
                if isinstance(eol_status, bool) and eol_status is False:
                    if "latest" in cycle_info and cycle_info["latest"]:
                        latest_version_str = cycle_info["latest"]
                        print(f"Latest stable (non-EOL cycle) Python version from API: {latest_version_str}")
                        return latest_version_str
            
            if data[0] and "latest" in data[0] and data[0]["latest"]:
                print("Warning: Could not find a definitively non-EOL Python cycle with a 'latest' version. Using the newest listed cycle's 'latest'.", file=sys.stderr)
                latest_version_str = data[0]["latest"]
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
    """
    target_version_str = version_str_override
    if not target_version_str:
        target_version_str = _get_latest_python_version_from_api()

    if target_version_str:
        base_ftp_url = constants.PYTHON_FTP_BASE_URL 
        filename = ""
        match = re.fullmatch(r"(\d+\.\d+\.\d+)", target_version_str)
        if not match:
            print(f"Invalid version string format: {target_version_str}. Expected X.Y.Z.", file=sys.stderr)
            return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK
        
        clean_version_str = match.group(1)

        if os_filter == "win64":
            filename = f"python-{clean_version_str}-amd64.exe"
        elif os_filter == "win32":
            filename = f"python-{clean_version_str}.exe" 
        elif os_filter == "macos":
            v_tuple = tuple(map(int, clean_version_str.split('.')))
            macos_ver_suffix = "macos11" 
            if v_tuple < (3, 9): 
                macos_ver_suffix = "macos10.9" 
            filename = f"python-{clean_version_str}-{macos_ver_suffix}.pkg"
        else:
            print(f"Unsupported OS filter for direct FTP URL: {os_filter}", file=sys.stderr)
            return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK

        if filename:
            direct_url = f"{base_ftp_url}/{clean_version_str}/{filename}"
            print(f"Constructed download URL: {direct_url}")
            return direct_url

    print("Could not determine Python version for download URL construction.", file=sys.stderr)
    return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK

def install_python_interactive(version_or_url: str, download_dir: pathlib.Path) -> bool:
    installer_url = None
    if version_or_url.lower() == "latest":
        installer_url = get_latest_python_download_url() 
    elif version_or_url.startswith("http://") or version_or_url.startswith("https://"):
        installer_url = version_or_url
    else: 
        print(f"Attempting to find installer URL for Python version: {version_or_url}")
        installer_url = get_latest_python_download_url(version_str_override=version_or_url)

    if not installer_url:
        print("Could not determine Python installer URL.", file=sys.stderr)
        return False

    installer_name = installer_url.split('/')[-1]
    if not (installer_name.endswith((".exe", ".pkg", ".dmg"))): 
        print(f"Warning: Download URL does not appear to point to a standard installer file: {installer_name}", file=sys.stderr)
        original_extension = pathlib.Path(installer_name).suffix
        safe_version_or_url = re.sub(r'[^\w\.-]', '_', version_or_url)
        installer_name = f"python_installer_{safe_version_or_url}{original_extension if original_extension and len(original_extension) <=4 else '.exe'}"
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

    try:
        print(f"Attempting to launch installer: {str(installer_path)}...")
        if os.name == 'nt':
            os.startfile(installer_path) 
            print("Installer launched (os.startfile). Please follow its instructions.")
        elif os.name == 'posix': 
            if installer_path.suffix == '.pkg':
                print(f"Attempting to open installer with default application: {installer_path}")
                system_utils.run_command(['open', str(installer_path)], check_return_code=False)
            else:
                print(f"Please make the installer executable (chmod +x {installer_path}) and run it manually.")
        else:
            print(f"Please run the downloaded installer from: {installer_path}")
        print("Installer process initiated. Please follow the prompts in the installer window.")
    except Exception as e:
        print(f"Could not automatically launch/open the installer: {e}", file=sys.stderr)
        print(f"Please navigate to '{installer_path.parent}' and run '{installer_path.name}' manually.")
    
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
        if not system_utils.prompt_user_for_confirmation("Proceed with upgrade guide anyway (not recommended)?"):
            return False

    print("\nStep 1: Backing up list of installed packages from the old Python...")
    requirements_content = None
    pip_freeze_cmd = [old_python_exe, "-m", "pip", "freeze"]
    freeze_result = system_utils.run_command(pip_freeze_cmd, capture_output=True, check_return_code=False)
    if freeze_result and freeze_result.returncode == 0 and freeze_result.stdout:
        requirements_content = freeze_result.stdout
        print("Successfully retrieved package list from old Python.")
    else:
        print("Warning: Could not retrieve package list from old Python.", file=sys.stderr)
        if not system_utils.prompt_user_for_confirmation("Continue upgrade without package migration?"):
            return False

    print("\nStep 2: Installing a new version of Python...")
    print("It is strongly recommended to install the new Python version to a DIFFERENT directory.")
    if not install_python_interactive("latest", download_dir): 
        print("Failed to initiate new Python installation. Aborting upgrade.", file=sys.stderr)
        return False
    
    print("\n--- IMPORTANT ---")
    print("After the new Python installer finishes, please provide the path to the new python.exe")
    print("Example: C:\\Python312\\python.exe or /usr/local/bin/python3.12")
    
    new_python_exe_str = ""
    while True: # Prompt user for the new Python path
        new_python_exe_str = input("Enter the full path to the new python.exe (or type 'skip' to skip package migration): ").strip().replace("\"", "")
        if new_python_exe_str.lower() == 'skip':
            requirements_content = None 
            new_python_exe_str = "" 
            print("Skipping package reinstallation.")
            break
        if not new_python_exe_str: 
            if system_utils.prompt_user_for_confirmation("No path entered. Skip package reinstallation for now?"):
                requirements_content = None 
                new_python_exe_str = ""
                break
            else:
                continue 
        
        new_python_info_temp = get_python_executable_info(new_python_exe_str)
        if new_python_info_temp:
            if pathlib.Path(new_python_info_temp['executable']).resolve() == pathlib.Path(old_python_exe).resolve():
                print("Error: The new Python path cannot be the same as the old Python path for an upgrade.", file=sys.stderr)
                print("Please install the new Python to a separate directory, or ensure you provide the correct new path.")
                continue 
            print(f"New Python identified: {new_python_info_temp['version_str']} at {new_python_info_temp['executable']}")
            if not system_utils.prompt_user_for_confirmation(f"Is this correct?"):
                continue 
            break 
        else:
            print(f"Path '{new_python_exe_str}' does not seem to be a valid Python executable. Please try again.")

    if not new_python_exe_str: 
        print("Python upgrade process finished (new Python installed). Package migration was skipped as no new Python path was confirmed.")
        if requirements_content:
            print(f"Your old package list was:\n{requirements_content}")
            print("You can manually reinstall them later.")
        return True 

    new_python_exe_info = get_python_executable_info(new_python_exe_str)
    if not new_python_exe_info: 
        print(f"Critical error: Could not re-verify new Python path {new_python_exe_str}", file=sys.stderr)
        return False
    new_python_exe = new_python_exe_info['executable']

    print(f"\nStep 3: Updating pip for the new Python at {new_python_exe}...")
    if not update_pip(new_python_exe):
        print("Warning: Failed to update pip for the new Python.", file=sys.stderr)
        if requirements_content and not system_utils.prompt_user_for_confirmation("Continue with package reinstallation despite pip update failure?"):
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
    if new_python_exe_str and new_python_exe_info: 
         print(f"New Python: {new_python_exe_info['executable']} (Version: {new_python_exe_info['version_str']})")
    else:
        print("New Python installation was guided, but path not confirmed for package migration or migration was skipped.")
    if requirements_content and new_python_exe_str : print("Attempted to migrate packages.")
    elif requirements_content and not new_python_exe_str : print("Package backup was created but migration was skipped.")
    else: print("Package migration was skipped or failed at backup stage.")
        
    print("\nRecommendation: You can now uninstall the old Python version if you are satisfied with the new setup.")
    print(f"Path to old Python: {old_python_exe}")
    return True

def ensure_python_in_path(python_exe_path: pathlib.Path | None = None) -> bool:
    print(f"Placeholder: ensure_python_in_path({python_exe_path}) called.", file=sys.stderr)
    print("Please ensure Python's Scripts directory and main directory are in your PATH.", file=sys.stderr)
    print("This is usually handled by the Python installer if you check 'Add Python to PATH'.")
    return False 