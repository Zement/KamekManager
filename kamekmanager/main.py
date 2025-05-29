# kamekmanager/main.py
import argparse
import sys
import os

# # To allow running from the project root and importing core modules
# # This might be adjusted based on how you structure/install the package later
# current_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = os.path.dirname(current_dir) # If main.py is in kamekmanager/
# if project_root not in sys.path:
#    sys.path.insert(0, project_root)
# # A more robust way if you make kamekmanager a package:
# # from .core import system_utils

from kamekmanager.core import system_utils
from kamekmanager.common import constants

def main():
    """Main entry point for the KamekManager CLI."""
    parser = argparse.ArgumentParser(description=f"{constants.APP_NAME} - A tool for managing NSMBW mods.")
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
    # Add more arguments here as functionality is built out
    # e.g., setup-env, check-env, list-modules, etc.

    args = parser.parse_args()

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
        # You might want to ensure it's created here if it doesn't exist
        # os.makedirs(data_dir, exist_ok=True)
        return

    print(f"Welcome to {constants.APP_NAME}!")
    print("Use --help for available commands.")

    # Example of how you might call other functions:
    # if not system_utils.check_admin_privileges():
    #     print("Warning: Not running as admin. Some operations might fail.")
    #     if not system_utils.prompt_user_for_confirmation("Continue without admin?"):
    #         sys.exit("Exiting.")

    # system_utils.initialize_workspace(system_utils.get_user_data_directory())


if __name__ == "__main__":
    main()