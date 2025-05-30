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

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False # Keep for potential fallback scraping if API fails

def get_python_executable_info(python_exe_path_str: str) -> dict | None:
    """Gets version and path for a given Python executable."""
    if not python_exe_path_str: # Handle empty string case
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
        return None
    try:
        api_url = "https://endoflife.date/api/python.json"
        print(f"Fetching latest Python version info from: {api_url}")
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        # The first entry is usually the newest release cycle still supported.
        # We need to find the one that is not EOL and is the latest.
        # The API sorts them by release date, so data[0] is the newest *cycle*.
        # We need its 'latest' field.
        if data and isinstance(data, list) and len(data) > 0:
            # Find the first non-EOL cycle, which should be the latest stable major.minor
            latest_cycle_info = None
            for cycle_info in data:
                if isinstance(cycle_info.get("eol"), bool) and cycle_info["eol"] is False: # Actively supported cycle
                    latest_cycle_info = cycle_info
                    break
                elif isinstance(cycle_info.get("eol"), str): # Date string, check if it's in the future or very recent
                     # This part can be complex if we need to parse dates.
                     # For now, assume the first one with "eol": false is good, or the absolute first if none.
                     latest_cycle_info = cycle_info # Fallback to newest listed if no "eol:false"
                     break


            if latest_cycle_info and "latest" in latest_cycle_info:
                latest_version_str = latest_cycle_info["latest"]
                print(f"Latest stable Python version from API: {latest_version_str}")
                return latest_version_str
        print("Could not parse latest Python version from API response.", file=sys.stderr)
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching latest Python version from API: {e}", file=sys.stderr)
        return None
    except Exception as e: # Catch other errors like JSONDecodeError
        print(f"Unexpected error processing API response for Python version: {e}", file=sys.stderr)
        return None

def get_latest_python_download_url(os_filter="win64") -> str | None:
    """
    Attempts to find the download URL for the latest stable Python installer.
    Uses endoflife.date API for version, then constructs FTP URL.
    Falls back to scraping python.org if API fails or for more specific links if needed.
    """
    latest_version_str = _get_latest_python_version_from_api()

    if latest_version_str:
        # Construct direct FTP URL based on common patterns
        # Example: [https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe](https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe)
        base_ftp_url = "https://www.python.org/ftp/python"
        filename = ""
        if os_filter == "win64":
            filename = f"python-{latest_version_str}-amd64.exe"
        elif os_filter == "win32":
            filename = f"python-{latest_version_str}.exe" # 32-bit often doesn't have -win32 suffix explicitly
        elif os_filter == "macos":
            # macOS universal2 installer is common
            # Example: python-3.12.3-macos11.pkg (macos11 or macos10.9 for older)
            # This part is trickier as the macOS filename can vary more.
            # We might need to scrape the specific version page or use the index.json for macOS.
            # For now, let's focus on Windows and provide a placeholder for macOS.
            print(f"MacOS installer URL construction for version {latest_version_str} is complex; consider manual URL or scraping fallback.", file=sys.stderr)
            filename = f"python-{latest_version_str}-macos11.pkg" # Educated guess
        else:
            print(f"Unsupported OS filter for direct FTP URL: {os_filter}", file=sys.stderr)
            return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK

        if filename:
            direct_url = f"{base_ftp_url}/{latest_version_str}/{filename}"
            print(f"Constructed direct download URL: {direct_url}")
            # We could add a HEAD request here to check if the URL actually exists before returning it.
            return direct_url

    # Fallback to scraping if API/direct construction fails (original method, slightly adjusted)
    print("Falling back to scraping python.org to find download URL...", file=sys.stderr)
    if not BS4_AVAILABLE or not REQUESTS_AVAILABLE: # Ensure requests is also checked for scraping
        print("Libraries 'requests' and 'beautifulsoup4' are required for scraping python.org.", file=sys.stderr)
        return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK

    base_url_scrape = "https://www.python.org"
    downloads_url_scrape = f"{base_url_scrape}/downloads/"
    try:
        print(f"Fetching {downloads_url_scrape} (scraping fallback)...")
        headers = {'User-Agent': 'Mozilla/5.0 KamekManager'}
        response = requests.get(downloads_url_scrape, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the link to the specific version's page (e.g., /downloads/release/python-3123/)
        # The main download button often links to this page.
        latest_version_page_link = soup.find('a', class_='button', string=re.compile(r"Download Python \d+\.\d+(\.\d+)?"))
        if not latest_version_page_link or not latest_version_page_link.get('href'):
            print("Scraping: Could not find the main download button link.", file=sys.stderr)
            return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK

        version_page_url_segment = latest_version_page_link['href']
        if not version_page_url_segment.startswith('/downloads/release/python-'):
            print(f"Scraping: Main download button link '{version_page_url_segment}' does not look like a release page link.", file=sys.stderr)
            return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK
        
        version_page_url = base_url_scrape + version_page_url_segment
        
        print(f"Fetching version specific page for scraping: {version_page_url}")
        response = requests.get(version_page_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        link_text_pattern = re.compile(r"Windows installer \(\s*64-bit\s*\)", re.IGNORECASE) if os_filter == "win64" else \
                            re.compile(r"Windows installer \(\s*32-bit\s*\)", re.IGNORECASE) if os_filter == "win32" else \
                            re.compile(r"macOS\s+64-bit\s+(universal2\s+)?installer", re.IGNORECASE) if os_filter == "macos" else None

        if not link_text_pattern:
            print(f"Scraping: Unsupported OS filter: {os_filter}", file=sys.stderr)
            return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK

        # Find the "Files" table
        files_table = soup.find('table', class_='files')
        if not files_table: # More generic search if class name changes
            release_content = soup.find('article', role='article') # Common container for release notes
            if release_content:
                files_table = release_content.find('table')

        if files_table:
            for anchor in files_table.find_all('a', string=link_text_pattern):
                if anchor.get('href') and anchor['href'].endswith(('.exe', '.pkg')): # Ensure it's a downloadable file
                    installer_url = anchor['href']
                    # URLs on the release page are usually absolute
                    if installer_url.startswith('http'):
                        print(f"Scraping: Found installer URL: {installer_url}")
                        return installer_url
        
        print(f"Scraping: Could not find a specific '{link_text_pattern.pattern}' link on {version_page_url}", file=sys.stderr)
        return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK

    except requests.exceptions.RequestException as e:
        print(f"Scraping fallback error: {e}", file=sys.stderr)
        return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK
    except Exception as e:
        print(f"Unexpected error during scraping fallback: {e}", file=sys.stderr)
        return constants.PYTHON_INSTALLER_URL_WIN_FALLBACK


def install_python_interactive(version_or_url: str, download_dir: pathlib.Path) -> bool:
    installer_url = None
    if version_or_url.lower() == "latest":
        print("Attempting to find the latest Python installer URL...")
        installer_url = get_latest_python_download_url()
    elif version_or_url.startswith("http://") or version_or_url.startswith("https://"):
        installer_url = version_or_url
    else: 
        # Try to construct a direct FTP URL for a specific version
        base_ftp_url = "[https://www.python.org/ftp/python](https://www.python.org/ftp/python)"
        # Basic assumption for Windows 64-bit filename
        filename = f"python-{version_or_url}-amd64.exe" 
        installer_url = f"{base_ftp_url}/{version_or_url}/{filename}"
        print(f"Constructed URL for version {version_or_url}: {installer_url}")
        # Could add a HEAD request here to check validity

    if not installer_url:
        print("Could not determine Python installer URL.", file=sys.stderr)
        return False

    installer_name = installer_url.split('/')[-1]
    if not (installer_name.endswith((".exe", ".pkg", ".dmg")) or "python_installer_downloaded" in installer_name):
        print(f"Warning: Download URL does not appear to point to a standard installer file: {installer_name}", file=sys.stderr)
        original_extension = pathlib.Path(installer_name).suffix
        installer_name = f"python_installer_{version_or_url.replace('.', '_')}{original_extension if original_extension else '.exe'}"
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
            os.startfile(installer_path)
            print("Installer launched. Please follow its instructions.")
        except Exception as e:
            print(f"Could not automatically launch the installer: {e}", file=sys.stderr)
            print(f"Please navigate to '{installer_path.parent}' and run '{installer_path.name}' manually.")
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
        stderr_output = ((result.stdout or "") + (result.stderr or "")).lower() # Combine outputs for check
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
    new_python_exe = get_python_executable_info(new_python_exe_str)['executable'] 
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
    if new_python_exe_str:
        new_py_info_final = get_python_executable_info(new_python_exe_str)
        if new_py_info_final:
             print(f"New Python: {new_py_info_final['executable']} (Version: {new_py_info_final['version_str']})")
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