# kamekmanager/common/constants.py

APP_NAME = "KamekManager"
APP_VERSION = "0.1.1-alpha" # Incremented version

# Target Python version for checks
MIN_PYTHON_VERSION = (3, 8) # Example: require Python 3.8+

# URLs (placeholders, update with actuals)
PYTHON_INSTALLER_URL_WIN = "[https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe](https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe)" # Example for 3.9
DEVKITPRO_UPDATER_URL = "[https://github.com/devkitPro/installer/releases/latest/download/devkitProUpdater-bootstrap.jar](https://github.com/devkitPro/installer/releases/latest/download/devkitProUpdater-bootstrap.jar)" # Check official source
# CODEWARRIOR_INSTALLER_URL = "YOUR_CW_INSTALLER_URL_HERE" # If you host it

# Default directory names within user_data_directory
DIR_NAME_GAME_SOURCES = "game_sources"
DIR_NAME_MODULES = "modules"
DIR_NAME_BUILD_OUTPUT = "build_output"
DIR_NAME_COMPILERS_TOOLS = "tools" 

# Required pip packages (can include versions)
PIP_PACKAGES = ["PyYAML>=5.0", "pyelftools>=0.27", "requests>=2.25"] # dataclasses is built-in for Python 3.7+

# Add other constants as needed