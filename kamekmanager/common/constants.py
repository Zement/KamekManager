# kamekmanager/common/constants.py

APP_NAME = "KamekManager"
APP_VERSION = "0.1.3-alpha" # Incremented version

# Target Python version for checks
MIN_PYTHON_VERSION = (3, 8) # Require Python 3.8+

# URLs (placeholders, update with actuals)
PYTHON_OFFICIAL_WEBSITE_URL = "https://www.python.org" 
PYTHON_FTP_BASE_URL = "https://www.python.org/ftp/python"
# Fallback URL if scraping/API fails for get_latest_python_download_url
PYTHON_INSTALLER_URL_WIN_FALLBACK = f"{PYTHON_FTP_BASE_URL}/3.13.3/python-3.13.3-amd64.exe" # Updated 2025-05-30

DEVKITPRO_UPDATER_URL = "https://github.com/devkitPro/installer/releases/latest/download/devkitProUpdater-bootstrap.jar" 
# CODEWARRIOR_INSTALLER_URL = "YOUR_CW_INSTALLER_URL_HERE" 

# Default directory names within user_data_directory
DIR_NAME_DOWNLOADS = "downloads" 
DIR_NAME_GAME_SOURCES = "game_sources"
DIR_NAME_MODULES = "modules"
DIR_NAME_BUILD_OUTPUT = "build_output"
DIR_NAME_COMPILERS_TOOLS = "tools" 

# Required pip packages (can include versions)
PIP_PACKAGES = ["PyYAML>=5.1", "pyelftools>=0.27", "requests>=2.25.0", "beautifulsoup4>=4.9.0"] 

# Add other constants as needed
