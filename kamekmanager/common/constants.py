# kamekmanager/common/constants.py

APP_NAME = "KamekManager"
APP_VERSION = "0.1.5-alpha" # Incremented version

# Target Python version for checks
MIN_PYTHON_VERSION = (3, 8) 

# URLs - Ensuring these are plain strings
PYTHON_OFFICIAL_WEBSITE_URL = "https://www.python.org"
PYTHON_FTP_BASE_URL = "https://www.python.org/ftp/python"
PYTHON_INSTALLER_URL_WIN_FALLBACK = f"{PYTHON_FTP_BASE_URL}/3.13.3/python-3.13.3-amd64.exe"

DEVKITPRO_UPDATER_URL = "https://github.com/devkitPro/installer/releases/download/v3.0.3/devkitProUpdater-3.0.3.exe"
CODEWARRIOR_INSTALLER_INFO_URL = "YOUR_CW_INFO_OR_DOWNLOAD_PAGE_HERE" # Placeholder

# Default directory names within user_data_directory
DIR_NAME_DOWNLOADS = "downloads" 
DIR_NAME_GAME_SOURCES = "game_sources"
DIR_NAME_MODULES = "modules"
DIR_NAME_BUILD_OUTPUT = "build_output"
DIR_NAME_COMPILERS_TOOLS = "tools" 

# Required pip packages
PIP_PACKAGES = ["PyYAML>=5.1", "pyelftools>=0.27", "requests>=2.25.0", "beautifulsoup4>=4.9.0"] 

# Environment Variables to check
DEVKITPRO_ENV_VAR = "DEVKITPRO"

# Key tool to verify DevkitPro tools/bin directory
DEVKITPRO_KEY_TOOL = "elf2dol.exe" 