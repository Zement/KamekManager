# kamekmanager/main.py
import argparse
import sys
import os
import pathlib # Added for install_python path handling

# Assuming main.py is in the root of your 'kamekmanager' package,
# and 'core' and 'common' are subdirectories/subpackages.
from kamekmanager.core import system_utils
from kamekmanager.core import python_env
from kamekmanager.common import constants

def main():
    """Main entry point for the KamekManager CLI."""
    parser = argparse.ArgumentParser(description=f"{constants.APP_NAME} - A tool for managing NSMBW mods.")
    
    # --- System Utils Arguments ---
    parser.add_argument(
        "--check-admin",
        action="store_true",
        help="Check if the script is running with admin privileges and exit."
    )
    parser.add_argument(
        "--show-data-dir",
        action="store_true",
        help="Show the user data directory for this application and exit."
    )

    # --- Python Env Arguments ---
    python_group = parser.add_argument_group('Python Environment Management')
    python_group.add_argument(
        "--check-python",
        action="store_true",
        help="Check for a suitable Python 3 installation and its version."
    )
    python_group.add_argument(
        "--install-pip-packages",
        nargs='*', 
        default=None, 
        metavar="PACKAGE_NAME",
        help=f"Check and install pip packages. If no package names are provided, installs default packages: {constants.PIP_PACKAGES}"
    )
    python_group.add_argument(
        "--get-latest-python-url",
        action="store_true",
        help="Attempt to find and print the download URL for the latest stable Python for Windows (64-bit)."
    )
    python_group.add_argument(
        "--install-python",
        metavar="VERSION_OR_URL",
        nargs="?", # Optional argument
        const="latest", # Value if argument is present without a value
        help="Download and guide Python installation. Optionally specify version (e.g., 3.9.13) or direct URL. 'latest' by default."
    )
    python_group.add_argument(
        "--upgrade-python",
        metavar="OLD_PYTHON_EXE",
        help="Guide the upgrade of an existing Python installation specified by its executable path."
    )


    args = parser.parse_args()

    # --- Handle System Util Commands ---
    if args.check_admin:
        is_admin = system_utils.check_admin_privileges()
        print(f"Running with administrative privileges." if is_admin else "Not running with administrative privileges.")
        return

    if args.show_data_dir:
        data_dir = system_utils.get_user_data_directory()
        print(f"User data directory: {data_dir}")
        return

    # --- Handle Python Env Commands ---
    if args.check_python:
        print("Checking Python installation...")
        python_info = python_env.check_python_installation(min_version=constants.MIN_PYTHON_VERSION)
        if python_info and python_info["version_str"]:
            print(f"Found compatible Python version: {python_info['version_str']} at {python_info['executable']}")
            if python_info["is_windows_store_app"]:
                print("Warning: This Python installation appears to be from the Microsoft Store, which may have limitations for development tools.")
        else:
            print(f"No compatible Python 3 (version {constants.MIN_PYTHON_VERSION[0]}.{constants.MIN_PYTHON_VERSION[1]}+) found or identified in PATH.")
            print(f"Please install Python {constants.MIN_PYTHON_VERSION[0]}.{constants.MIN_PYTHON_VERSION[1]} or newer and ensure it's added to your PATH.")
        return

    if args.install_pip_packages is not None:
        packages_to_install = args.install_pip_packages if args.install_pip_packages else constants.PIP_PACKAGES
        if not packages_to_install:
             print("No packages specified for installation and no default packages defined.")
        else:
            print(f"Checking and installing pip packages for current Python ({sys.executable}): {', '.join(packages_to_install)}")
            if not python_env.update_pip(sys.executable): 
                 print("Failed to update pip. Package installation might fail or use an old version.")
            success = python_env.check_and_install_pip_packages(sys.executable, packages_to_install)
            print("Pip package check/installation process completed." if success else "Pip package check/installation encountered issues.")
        return
        
    if args.get_latest_python_url:
        print("Attempting to find the latest Python download URL for Windows (64-bit)...")
        url = python_env.get_latest_python_download_url()
        if url:
            print(f"Found URL: {url}")
        else:
            print("Could not automatically determine the latest Python download URL.")
        return

    if args.install_python:
        if not system_utils.check_admin_privileges():
            print(f"Error: Administrative privileges are required to install Python system-wide or update PATH.")
            print("Please re-run KamekManager as an administrator.")
            sys.exit(1)
        
        version_or_url = args.install_python
        print(f"Starting Python installation process for: {version_or_url}")
        
        download_dir = system_utils.get_user_data_directory() / constants.DIR_NAME_DOWNLOADS
        download_dir.mkdir(parents=True, exist_ok=True)
        
        if python_env.install_python_interactive(version_or_url, download_dir):
            print("Python installation process initiated. Follow the installer prompts.")
            print("Remember to check 'Add Python to PATH' if the installer offers it.")
        else:
            print("Python installation process failed to start.")
        return

    if args.upgrade_python:
        if not system_utils.check_admin_privileges():
            print(f"Error: Administrative privileges are required to install a new Python version and manage PATH.")
            print("Please re-run KamekManager as an administrator.")
            sys.exit(1)

        old_python_exe_path = pathlib.Path(args.upgrade_python)
        if not old_python_exe_path.is_file():
            print(f"Error: Provided Python executable path is not valid: {old_python_exe_path}")
            sys.exit(1)
        
        print(f"Starting Python upgrade process for: {old_python_exe_path}")
        download_dir = system_utils.get_user_data_directory() / constants.DIR_NAME_DOWNLOADS
        
        if python_env.upgrade_python_interactive(str(old_python_exe_path), download_dir):
            print("Python upgrade process completed or initiated.")
        else:
            print("Python upgrade process failed.")
        return

    print(f"Welcome to {constants.APP_NAME} {constants.APP_VERSION}!")
    print("Use --help for available commands.")

if __name__ == "__main__":
    main()