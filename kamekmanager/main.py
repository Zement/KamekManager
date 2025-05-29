# kamekmanager/main.py
import argparse
import sys
import os

# Assuming main.py is in the root of your 'kamekmanager' package,
# and 'core' and 'common' are subdirectories/subpackages.
# If KamekManager/kamekmanager/main.py is your structure,
# and you run from KamekManager/
# python -m kamekmanager.main
# then these imports should work:
from core import system_utils
from core import python_env # New import
from common import constants

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
    parser.add_argument(
        "--check-python",
        action="store_true",
        help="Check for a suitable Python 3 installation and its version."
    )
    parser.add_argument(
        "--install-pip-packages",
        nargs='*', # 0 or more arguments
        default=None, # Default if argument not present
        metavar="PACKAGE_NAME",
        help=f"Check and install required pip packages. If no package names are provided, installs default packages: {constants.PIP_PACKAGES}"
    )


    # Add more arguments here as functionality is built out
    # e.g., setup-env, check-env, list-modules, etc.

    args = parser.parse_args()

    # --- Handle System Util Commands ---
    if args.check_admin:
        is_admin = system_utils.check_admin_privileges()
        if is_admin:
            print(f"Running with administrative privileges.")
        else:
            print(f"Not running with administrative privileges.")
            print(f"Some operations in {constants.APP_NAME} may require admin rights.")
        return

    if args.show_data_dir:
        data_dir = system_utils.get_user_data_directory()
        print(f"User data directory: {data_dir}")
        # os.makedirs(data_dir, exist_ok=True) # Already handled in get_user_data_directory
        return

    # --- Handle Python Env Commands ---
    if args.check_python:
        print("Checking Python installation...")
        python_version = python_env.check_python_installation(min_version=constants.MIN_PYTHON_VERSION)
        if python_version:
            print(f"Found compatible Python version: {python_version}")
        else:
            print(f"No compatible Python 3 installation (version {constants.MIN_PYTHON_VERSION[0]}.{constants.MIN_PYTHON_VERSION[1]}+) found in PATH.")
            print(f"Please install Python {constants.MIN_PYTHON_VERSION[0]}.{constants.MIN_PYTHON_VERSION[1]} or newer and ensure it's added to your PATH.")
        return

    if args.install_pip_packages is not None: # Triggered if --install-pip-packages is present
        packages_to_install = args.install_pip_packages if args.install_pip_packages else constants.PIP_PACKAGES
        if not packages_to_install:
             print("No packages specified for installation and no default packages defined.")
        else:
            print(f"Checking and installing pip packages: {', '.join(packages_to_install)}")
            success = python_env.check_and_install_pip_packages(packages_to_install)
            if success:
                print("All specified pip packages are installed or were successfully installed.")
            else:
                print("There was an issue checking or installing some pip packages. Please see logs above.")
        return
        

    print(f"Welcome to {constants.APP_NAME}!")
    print("Use --help for available commands.")

    # Example of how you might call other functions:
    # if not system_utils.check_admin_privileges():
    #     print("Warning: Not running as admin. Some operations might fail.")
    #     if not system_utils.prompt_user_for_confirmation("Continue without admin?"):
    #         sys.exit("Exiting.")

    # Example: Initialize workspace if other commands are to be run
    # workspace_paths = system_utils.initialize_workspace(system_utils.get_user_data_directory())
    # if not workspace_paths:
    #    print("Failed to initialize workspace. Exiting.")
    #    sys.exit(1)


if __name__ == "__main__":
    main()