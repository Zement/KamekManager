# kamekmanager/core/__init__.py
# This file makes Python treat the `core` directory as a package.

# Make key functions easily accessible via `from core import ...`
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

from .python_env import ( # New functions
    check_python_installation,
    install_python, # Placeholder for now
    ensure_python_in_path, # Placeholder for now
    check_and_install_pip_packages
)

# You might also want to define __all__ if you want `from core import *` to behave predictably
# __all__ = [
# "check_admin_privileges", "get_user_data_directory", ...
# "check_python_installation", ...
# ]