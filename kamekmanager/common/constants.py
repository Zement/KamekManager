# kamekmanager/common/constants.py

APP_NAME = "KamekManager"
APP_VERSION = "0.1.0-alpha"

# URLs (placeholders, update with actuals)
PYTHON_INSTALLER_URL_WIN = "https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe" # Example
DEVKITPRO_UPDATER_URL = "https://github.com/devkitPro/installer/releases/latest/download/devkitProUpdater-bootstrap.jar" # Check official source
# CODEWARRIOR_INSTALLER_URL = "YOUR_CW_INSTALLER_URL_HERE" # If you host it

# Default directory names within user_data_directory
DIR_NAME_GAME_SOURCES = "game_sources"
DIR_NAME_MODULES = "modules"
DIR_NAME_BUILD_OUTPUT = "build_output"
DIR_NAME_COMPILERS_TOOLS = "tools" # For downloaded compilers/tools if not installed system-wide

# Required pip packages
PIP_PACKAGES = ["PyYAML", "pyelftools"] # dataclasses is built-in for Python 3.7+

# Add other constants as needed