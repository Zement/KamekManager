# kamekmanager/core/__init__.py
# This file makes Python treat the `core` directory as a package.

from .system_utils import (
    check_admin_privileges,
    get_user_data_directory,
    run_command,
    set_environment_variable,
    get_environment_variable,
    is_program_in_path,
    add_directory_to_system_path,
    download_file,
    extract_zip,
    prompt_user_for_confirmation
)

from .python_env import (
    check_python_installation,
    install_python_interactive, 
    upgrade_python_interactive, 
    ensure_python_in_path, 
    check_and_install_pip_packages,
    get_latest_python_download_url, 
    update_pip 
)