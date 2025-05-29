# kamekmanager/core/python_env.py
# New file for Python environment management functions
import sys
import subprocess
import importlib.util # For checking if a module can be imported
import pathlib

from .system_utils import run_command # Use our own run_command
from common import constants

def check_python_installation(min_version: tuple = constants.MIN_PYTHON_VERSION) -> str | None:
    """
    Checks if a suitable Python 3.x version is installed and in PATH.
    Verifies `python` or `python3` command. Checks `sys.version_info`.
    Args:
        min_version: A tuple like (3, 7) for minimum required Python version.
    Returns:
        The full version string of the suitable Python 3 found, or None.
    """
    python_exe = sys.executable # Path to current Python interpreter
    
    if not python_exe:
        print("Could not determine current Python interpreter path (sys.executable is empty).", file=sys.stderr)
        # Try to find python in PATH as a fallback, though this is less reliable
        # if the script isn't being run by the desired python.
        for cmd_name in ["python3", "python"]:
            check_path = run_command([cmd_name, "--version"], capture_output=True, check_return_code=False)
            if check_path and check_path.returncode == 0:
                # This found *a* python, but sys.version_info is about the *current* one.
                # This block is more for if sys.executable was somehow None.
                # For now, rely on sys.executable and sys.version_info primarily.
                pass # Further logic would be needed here if sys.executable is truly unusable.

    current_version_info = sys.version_info
    current_version_str = f"{current_version_info.major}.{current_version_info.minor}.{current_version_info.micro}"

    print(f"Current Python interpreter: {python_exe}")
    print(f"Current Python version: {current_version_str}")

    if current_version_info.major == 2:
        print(f"Warning: The current Python is Python 2 ({current_version_str}). This tool requires Python 3.", file=sys.stderr)
        # Attempt to find Python 3 specifically
        py3_check = run_command(["python3", "--version"], capture_output=True, check_return_code=False)
        if py3_check and py3_check.returncode == 0:
            # This means python3 is in path, but the script was run with python2
            print("A 'python3' command was found. Please re-run this tool using 'python3 main.py ...'", file=sys.stderr)
            # We could try to parse py3_check.stdout/stderr for its version, but it's better to enforce user runs with py3.
        return None # Indicate Python 2 is not suitable.

    if current_version_info.major < min_version[0] or \
       (current_version_info.major == min_version[0] and current_version_info.minor < min_version[1]):
        print(f"Installed Python version {current_version_str} is older than required {min_version[0]}.{min_version[1]}+.", file=sys.stderr)
        return None
    
    # Check for Python 2 in PATH if 'python' command exists and points to it
    # This is more of a warning if the user might accidentally use 'python' for other things.
    python_cmd_check = run_command(["python", "--version"], capture_output=True, check_return_code=False)
    if python_cmd_check and python_cmd_check.returncode == 0:
        output = (python_cmd_check.stdout or "") + (python_cmd_check.stderr or "")
        if "Python 2." in output:
            print("Warning: The 'python' command in your PATH seems to point to Python 2.", file=sys.stderr)
            print("Ensure you use 'python3' or the direct path to your Python 3 interpreter for Python 3 tasks.", file=sys.stderr)

    return current_version_str # Return the version string of the currently running, compatible Python

def install_python(version_to_install: str = "3.9.x") -> bool:
    """
    Downloads and silently installs a specific Python version. (Placeholder)
    Details: Fetches official installer, uses silent install switches. Ensures it's added to PATH.
    THIS IS A COMPLEX FUNCTION and highly OS-dependent.
    Returns: True on success, False otherwise.
    """
    print(f"Placeholder: install_python({version_to_install}) called.", file=sys.stderr)
    print("Automatic Python installation is a complex feature and not yet implemented.", file=sys.stderr)
    if os.name == 'nt':
        print(f"You would typically download from: {constants.PYTHON_INSTALLER_URL_WIN}", file=sys.stderr)
        print("And run with silent switches like: /quiet InstallAllUsers=1 PrependPath=1 TargetDir=C:\\Python39", file=sys.stderr)
    else:
        print("On Linux/macOS, Python is often installed via package managers (apt, yum, brew) or pyenv.", file=sys.stderr)
    return False # Not implemented

def ensure_python_in_path(python_exe_path: pathlib.Path | None = None) -> bool:
    """
    If Python is installed but not in PATH, this attempts to add it. (Placeholder)
    Details: If python_exe_path is known, adds its directory to PATH.
    Returns: True if Python is now in PATH or was already, False otherwise.
    """
    print(f"Placeholder: ensure_python_in_path({python_exe_path}) called.", file=sys.stderr)
    print("Automatic PATH modification for Python is not yet implemented.", file=sys.stderr)
    # This would involve calling system_utils.add_directory_to_system_path
    # with the parent directory of python_exe_path.
    # Requires admin rights and careful handling.
    return False # Not implemented

def check_and_install_pip_packages(packages: list[str]) -> bool:
    """
    Checks if required pip packages are installed and installs them if missing.
    Uses `sys.executable -m pip install <package>`.
    Args:
        packages: A list of package names to check/install (e.g., ["PyYAML", "requests"]).
    Returns:
        True if all packages are present or installed successfully, False otherwise.
    """
    if not packages:
        print("No pip packages specified to check or install.")
        return True # No packages, so technically successful

    all_successful = True
    for package_spec in packages:
        # Pip can install from name, name==version, name>=version, etc.
        # For checking, we usually just need the package name.
        package_name = package_spec.split('==')[0].split('>=')[0].split('<=')[0].split('!=')[0].split('~=')[0]
        
        try:
            # Check if package is importable
            # This is a common way to check, but not foolproof for all packages
            # (e.g., if import name differs from pip package name, like 'python-dotenv' vs 'dotenv')
            # For packages like PyYAML (import yaml) or pyelftools (import elftools), this works.
            # A more robust check is `pip show <package_name>`.
            
            # Using pip show for checking
            pip_show_cmd = [sys.executable, "-m", "pip", "show", package_name]
            result = run_command(pip_show_cmd, capture_output=True, check_return_code=False)

            if result and result.returncode == 0:
                print(f"Package '{package_name}' (from spec '{package_spec}') is already installed.")
                # Could parse `pip show` output for version if needed.
            else:
                print(f"Package '{package_name}' (from spec '{package_spec}') not found or `pip show` failed. Attempting to install...")
                # Install the package using the full specifier (e.g., 'requests>=2.0')
                pip_install_cmd = [sys.executable, "-m", "pip", "install", package_spec]
                install_result = run_command(pip_install_cmd, display_output_live=True, check_return_code=True) # Display live output
                
                if install_result and install_result.returncode == 0:
                    print(f"Successfully installed '{package_spec}'.")
                else:
                    print(f"Failed to install '{package_spec}'.", file=sys.stderr)
                    all_successful = False
        except Exception as e:
            print(f"An error occurred while checking/installing package '{package_spec}': {e}", file=sys.stderr)
            all_successful = False
            
    return all_successful