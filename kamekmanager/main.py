# kamekmanager/main.py
import argparse
import sys
import os
import pathlib 

from kamekmanager.core import system_utils
from kamekmanager.core import python_env
from kamekmanager.core import toolchain_setup 
from kamekmanager.common import constants

def main():
    """Main entry point for the KamekManager CLI."""
    parser = argparse.ArgumentParser(description=f"{constants.APP_NAME} - A tool for managing NSMBW mods.")
    
    # --- System Utils Arguments ---
    sys_group = parser.add_argument_group('System Utilities')
    sys_group.add_argument(
        "--check-admin",
        action="store_true",
        help="Check if the script is running with admin privileges and exit."
    )
    sys_group.add_argument(
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
        help=f"Check and install pip packages for current Python. Defaults to: {constants.PIP_PACKAGES}"
    )
    python_group.add_argument(
        "--get-latest-python-url",
        action="store_true",
        help="Attempt to find and print the download URL for the latest stable Python for Windows (64-bit)."
    )
    python_group.add_argument(
        "--install-python",
        metavar="VERSION_OR_URL",
        nargs="?", 
        const="latest", 
        help="Download and guide Python installation. Specify version (e.g., 3.9.13), URL, or 'latest'."
    )
    python_group.add_argument(
        "--upgrade-python",
        metavar="OLD_PYTHON_EXE_PATH",
        help="Guide the upgrade of an existing Python installation specified by its executable path."
    )

    # --- Toolchain Arguments ---
    toolchain_group = parser.add_argument_group('Modding Toolchain Management')
    toolchain_group.add_argument(
        "--check-devkitpro",
        action="store_true",
        help="Check for DevkitPPC installation and configuration."
    )
    toolchain_group.add_argument(
        "--install-devkitpro",
        action="store_true",
        help="Guide the installation/update of DevkitPPC."
    )
    # Add CodeWarrior check/install arguments later

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
                print("Warning: This Python installation appears to be from the Microsoft Store.")
        else:
            print(f"No compatible Python ({constants.MIN_PYTHON_VERSION[0]}.{constants.MIN_PYTHON_VERSION[1]}+) found or identified.")
        return

    if args.install_pip_packages is not None:
        packages_to_install = args.install_pip_packages if args.install_pip_packages else constants.PIP_PACKAGES
        if not packages_to_install:
             print("No packages specified for installation.")
        else:
            print(f"Managing pip packages for current Python ({sys.executable}): {', '.join(packages_to_install)}")
            if not python_env.update_pip(sys.executable):
                 print("Warning: Failed to update pip. Package installation might fail.")
            success = python_env.check_and_install_pip_packages(sys.executable, packages_to_install)
            print("Pip package management completed." if success else "Pip package management encountered issues.")
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
            print(f"Error: Admin privileges required to install Python or update PATH. Re-run as administrator.")
            sys.exit(1)
        version_or_url = args.install_python
        print(f"Starting Python installation process for: {version_or_url}")
        download_dir = system_utils.get_user_data_directory() / constants.DIR_NAME_DOWNLOADS
        if python_env.install_python_interactive(version_or_url, download_dir):
            print("Python installation process initiated. Follow installer prompts.")
        else:
            print("Python installation process failed to start.")
        return

    if args.upgrade_python:
        if not system_utils.check_admin_privileges():
            print(f"Error: Admin privileges required to install Python or manage PATH. Re-run as administrator.")
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

    # --- Handle Toolchain Commands ---
    if args.check_devkitpro:
        print("Checking for DevkitPPC installation...")
        devkitpro_info = toolchain_setup.check_devkitpro_installation()
        if devkitpro_info:
            print(f"DevkitPPC (DEVKITPRO) appears to be installed.")
            print(f"  DEVKITPRO Environment Variable: {devkitpro_info['DEVKITPRO_ENV']}")
            
            resolved_path_obj = pathlib.Path(devkitpro_info['resolved_path'])
            print(f"  Resolved DEVKITPRO Path: {resolved_path_obj}")
            
            print(f"  Key tool '{constants.DEVKITPRO_KEY_TOOL}' found: {'Yes' if devkitpro_info['key_tool_found'] else 'No'}")
            
            msys2_bin_path_str = str(resolved_path_obj / "msys2" / "usr" / "bin")
            print(f"  DevkitPro MSYS2 bin path ('{msys2_bin_path_str}') in system PATH: {'Yes' if devkitpro_info['msys2_bin_in_path'] else 'No (Important for command-line builds!)'}")
            
            if not devkitpro_info['msys2_bin_in_path']:
                 print(f"  To ensure compilers are found by build scripts, the DevkitPro installer typically adds '{msys2_bin_path_str}' to your system PATH.")
                 print(f"  Please verify your PATH settings if command-line builds fail to find compilers.")
                 # Optionally, still list other potentially useful paths for user awareness
                 devkitppc_bin = resolved_path_obj / "devkitPPC" / "bin"
                 tools_bin = resolved_path_obj / "tools" / "bin"
                 print(f"  Other potentially relevant DevkitPro paths (usually not needed in system PATH if MSYS2 path is set):")
                 print(f"    - {devkitppc_bin} (devkitPPC compilers)")
                 print(f"    - {tools_bin} (other DevkitPro utilities)")
        else:
            print("DevkitPPC (DEVKITPRO) not found or not correctly configured.")
        return
    
    if args.install_devkitpro:
        if not system_utils.check_admin_privileges(): 
            print(f"Error: Admin privileges may be required to install DevkitPPC. Re-run as administrator.")
            sys.exit(1)
        print("Starting DevkitPPC installation/update process...")
        download_dir = system_utils.get_user_data_directory() / constants.DIR_NAME_DOWNLOADS
        if toolchain_setup.install_devkitpro_interactive(download_dir):
            print("DevkitPPC installation process completed.")
        else:
            print("DevkitPPC installation process failed to start.")
        return

    print(f"Welcome to {constants.APP_NAME} {constants.APP_VERSION}!")
    print("Use --help for available commands.")

if __name__ == "__main__":
    main()