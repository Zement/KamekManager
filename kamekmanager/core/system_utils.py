# kamekmanager/core/system_utils.py
import os
import sys
import ctypes
import pathlib
import subprocess
import shutil
# We'll need 'requests' for download_file, ensure it's in your requirements.txt later
# import requests 
import zipfile

# Assuming constants.py is in a sibling 'common' directory.
# If your project structure is KamekManager/kamekmanager/core and KamekManager/kamekmanager/common
# then this import should work if you run as a module from KamekManager/
# python -m kamekmanager.main
from common import constants


def check_admin_privileges() -> bool:
    """
    Determines if the script is running with administrative privileges.
    Necessary for tasks like modifying the system PATH or installing software for all users.
    Uses platform-specific methods (e.g., ctypes on Windows).
    Returns: True if admin, False otherwise.
    """
    if os.name == 'nt': # Windows
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except AttributeError: # Fallback if shell32 or IsUserAnAdmin is not available
             print("Could not determine admin status using ctypes.windll.shell32.IsUserAnAdmin().", file=sys.stderr)
             # Attempt an alternative check: try to open a restricted file for writing.
             # This is more involved and has side effects, so often not preferred.
             # For now, assume not admin if the primary method fails.
             return False
        except Exception as e:
            print(f"Error checking admin privileges: {e}", file=sys.stderr)
            return False
    elif os.name == 'posix': # Linux/macOS
        # On POSIX systems, UID 0 is root
        return os.geteuid() == 0
    else:
        print(f"Unsupported OS for admin check: {os.name}", file=sys.stderr)
        return False # Or raise an exception

def get_user_data_directory(tool_name: str = constants.APP_NAME) -> pathlib.Path:
    """
    Determines and creates the base directory for storing tool-specific data.
    Uses platform-appropriate locations.
    Returns: A pathlib.Path object to the data directory.
    """
    if os.name == 'nt': # Windows
        # Typically %APPDATA%\ToolName
        app_data_dir = os.getenv('APPDATA')
        if app_data_dir:
            path = pathlib.Path(app_data_dir) / tool_name
        else:
            # Fallback if APPDATA is not set (unlikely for modern Windows)
            path = pathlib.Path.home() / f".{tool_name.replace(' ', '_')}_config" # Make it a hidden-like folder
    elif os.name == 'posix': # Linux/macOS
        # Typically ~/.config/ToolName or ~/.local/share/ToolName
        xdg_config_home = os.getenv('XDG_CONFIG_HOME')
        if xdg_config_home:
            path = pathlib.Path(xdg_config_home) / tool_name.replace(' ', '_')
        else:
            path = pathlib.Path.home() / ".config" / tool_name.replace(' ', '_')
    else:
        # Fallback for other OSes
        path = pathlib.Path.home() / f".{tool_name.replace(' ', '_')}_config"
    
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating data directory {path}: {e}", file=sys.stderr)
        # Depending on how critical this is, you might want to raise the exception
        # or return a default path / handle it gracefully. For now, we let it pass and return the path.
    return path

def run_command(
    command_parts: list[str], 
    working_directory: str | os.PathLike | None = None, 
    capture_output: bool = True, 
    check_return_code: bool = True, # Changed default behavior slightly
    display_output_live: bool = False,
    env: dict | None = None # Allow passing custom environment variables
) -> subprocess.CompletedProcess | None:
    """
    A wrapper around subprocess.run() to execute external commands.
    
    Args:
        command_parts: List of strings forming the command and its arguments.
        working_directory: The directory from which to run the command.
        capture_output: If True, stdout and stderr are captured.
        check_return_code: If True, and command returns non-zero, an error is printed and None is returned.
                           If False, the CompletedProcess object is returned regardless of exit code.
        display_output_live: If True, prints stdout/stderr as it's generated.
        env: A dictionary of environment variables to use for the new process.

    Returns:
        subprocess.CompletedProcess object or None if check_return_code is True and command fails.
    """
    try:
        command_str = ' '.join(str(part) for part in command_parts) # Ensure all parts are strings for join
        print(f"Running command: {command_str}")
        if working_directory:
            print(f"In directory: {working_directory}")

        if display_output_live:
            # This streams output directly.
            process = subprocess.Popen(command_parts, 
                                       cwd=working_directory,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, # Combine stdout and stderr
                                       text=True,
                                       bufsize=1, # Line buffered
                                       universal_newlines=True,
                                       env=env) # Pass custom env
            if process.stdout:
                for line in process.stdout:
                    print(line, end='') # Print live output
            process.wait() # Wait for the process to complete
            
            # Create a CompletedProcess-like object for consistency
            result = subprocess.CompletedProcess(args=command_parts, 
                                                returncode=process.returncode,
                                                stdout=None, # Output was already printed
                                                stderr=None) 
        else:
            result = subprocess.run(
                command_parts,
                cwd=working_directory,
                capture_output=capture_output,
                text=True,
                check=False, # We'll check the return code manually based on check_return_code arg
                env=env # Pass custom env
            )

        if check_return_code and result.returncode != 0:
            print(f"Command failed with exit code {result.returncode}: {command_str}", file=sys.stderr)
            if result.stdout and not display_output_live:
                print(f"STDOUT:\n{result.stdout}", file=sys.stderr)
            if result.stderr and not display_output_live: # stderr might be in stdout if redirected in Popen
                print(f"STDERR:\n{result.stderr}", file=sys.stderr)
            return None # Indicate failure
        return result # Return result regardless of exit code if check_return_code is False
    except FileNotFoundError:
        print(f"Error: Command not found - {command_parts[0]}. Is it in PATH or an absolute path?", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An error occurred while running command {command_str}: {e}", file=sys.stderr)
        return None

def set_environment_variable(name: str, value: str, is_system_wide: bool = True) -> bool:
    """
    Persistently sets an environment variable (Windows specific using setx).
    WARNING: On Windows, `setx` has a 1024 char limit for the combined PATH.
             Modifying PATH programmatically is risky and should be done with extreme care.
    Args:
        name: Name of the environment variable.
        value: Value to set.
        is_system_wide: If True, sets for all users (requires admin), else for current user.
    Returns: True on success, False otherwise.
    """
    if os.name == 'nt':
        if not check_admin_privileges() and is_system_wide:
            print(f"Admin privileges required to set system-wide environment variable '{name}'.", file=sys.stderr)
            print("Please re-run as administrator or set for current user only.", file=sys.stderr)
            return False
        
        # Ensure value is quoted if it contains spaces for setx
        quoted_value = f'"{value}"' if " " in value else value
        command = ['setx', name, quoted_value]
        if is_system_wide:
            command.append('/M')
        
        print(f"Attempting to set environment variable: {' '.join(command)}")
        # For setx, we usually don't want to check the return code strictly as it can be non-zero
        # even on success if the variable was set to the same value.
        # We also don't need to capture output unless debugging.
        result = run_command(command, capture_output=True, check_return_code=False) 
        
        # setx success is tricky. It might return 0 or 1.
        # A common check is if stderr is empty or contains specific success messages.
        # For simplicity, we'll consider it a success if the command ran.
        # A more robust check would involve querying the registry or `set` output in a new shell.
        if result is not None: # Command executed
            print(f"Environment variable '{name}' set. You may need to restart your shell or PC for changes to take effect.")
            # Verification step (optional, and might require new shell)
            # current_val_in_proc = get_environment_variable(name) # This gets current process env
            # print(f"Note: Current process sees '{name}' as '{current_val_in_proc}'. New shells will see the updated value.")
            return True
        else:
            print(f"Failed to execute setx command for '{name}'.", file=sys.stderr)
            return False
    else:
        print(f"Setting persistent environment variables programmatically is not directly supported for {os.name} in this script.", file=sys.stderr)
        print(f"Please set '{name}' to '{value}' manually in your shell configuration (e.g., .bashrc, .zshrc).", file=sys.stderr)
        return False

def get_environment_variable(name: str) -> str | None:
    """
    Retrieves the value of an environment variable.
    Returns: The variable's value or None if not found.
    """
    return os.getenv(name)

def is_program_in_path(program_name: str) -> bool:
    """
    Checks if a program/executable is findable via the system's PATH.
    Uses shutil.which().
    Returns: True if found, False otherwise.
    """
    return shutil.which(program_name) is not None

def add_directory_to_system_path(directory: str) -> bool:
    """
    Appends a directory to the system PATH variable persistently (Windows specific using setx).
    WARNING: This is a DANGEROUS operation. `setx` truncates PATH if it exceeds 1024 chars.
             It's generally safer to guide the user to do this manually.
    Returns: True on success, False otherwise.
    """
    if os.name == 'nt':
        if not check_admin_privileges():
            print("Admin privileges required to modify system PATH.", file=sys.stderr)
            return False

        # Normalize directory path
        norm_directory = str(pathlib.Path(directory).resolve())

        # To check if it's already in PATH, we need the *persistent* system PATH.
        # This is complex. `os.getenv("PATH")` is the current process's PATH.
        # A simple check against os.getenv("PATH") can be misleading for system-wide changes.
        # For now, we'll proceed with caution.
        
        # A robust way to get the *system* PATH on Windows is via the registry:
        # HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\Environment -> Path (REG_EXPAND_SZ or REG_SZ)
        # Or for *user* PATH:
        # HKEY_CURRENT_USER\Environment -> Path
        # This is beyond simple `setx` for checking.

        # If we're just appending, we rely on `setx` to handle the existing PATH.
        # The command `setx PATH "%PATH%;<new_dir>"` uses the *current* value of PATH *as seen by setx*.
        # If setting system-wide (`/M`), it should use the system PATH.
        
        print(f"WARNING: Modifying system PATH is risky. Ensure backups or manual restoration capability.")
        print(f"Attempting to add '{norm_directory}' to system PATH.")
        
        # Command to append using setx's own %PATH% expansion.
        # The value itself needs to be the new directory. setx handles the append.
        # No, setx PATH "C:\new\path;%PATH%" /M is the way to prepend
        # setx PATH "%PATH%;C:\new\path" /M is the way to append
        command = ['setx', 'PATH', f"%PATH%;{norm_directory}", '/M']
        
        result = run_command(command, capture_output=True, check_return_code=False)
        if result is not None: # Command executed
            print(f"Directory '{norm_directory}' command to add to PATH executed. Restart your shell or PC.")
            print("IMPORTANT: Verify your PATH variable. `setx` can truncate it if it's too long (over 1024 characters for the whole PATH).")
            return True
        else:
            print(f"Failed to execute command to add '{norm_directory}' to PATH.", file=sys.stderr)
            return False
    else:
        print("Automatic PATH modification is not supported for this OS. Please add manually.", file=sys.stderr)
        return False

def download_file(url: str, destination_path: pathlib.Path, show_progress: bool = True) -> bool:
    """
    Downloads a file from a URL.
    Uses 'requests' library.
    Returns: True on successful download, False otherwise.
    """
    try:
        import requests # Moved import here to avoid hard dependency if not used
        print(f"Downloading {url} to {destination_path}...")
        # Add headers to mimic a browser request, can help with some servers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, stream=True, timeout=60, headers=headers) # Increased timeout
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192 # 8KB
        
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        with open(destination_path, 'wb') as f:
            if show_progress and total_size > 0:
                downloaded_size = 0
                print(f"File size: {total_size / (1024*1024):.2f} MB")
                for chunk in response.iter_content(chunk_size=block_size):
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    progress = int(50 * downloaded_size / total_size)
                    # Ensure progress doesn't exceed 50 for display
                    progress = min(progress, 50)
                    # Calculate percentage for display
                    percentage = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                    sys.stdout.write(f"\r[{'#' * progress}{'.' * (50 - progress)}] {percentage:.2f}% ({downloaded_size // 1024}KB / {total_size // 1024}KB)")
                    sys.stdout.flush()
                sys.stdout.write('\n')
            else:
                for chunk in response.iter_content(chunk_size=block_size):
                    f.write(chunk)
        print(f"Download complete: {destination_path}")
        return True
    except ImportError:
        print("The 'requests' library is required for downloading. Please install it (`pip install requests`).", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}", file=sys.stderr)
        if destination_path.exists():
            try:
                destination_path.unlink()
            except OSError: pass
        return False
    except Exception as e:
        print(f"An unexpected error occurred during download of {url}: {e}", file=sys.stderr)
        return False


def extract_zip(zip_path: pathlib.Path, extract_to_dir: pathlib.Path) -> bool:
    """
    Extracts contents of a ZIP archive.
    Uses zipfile module.
    Returns: True on success, False otherwise.
    """
    try:
        if not zip_path.exists():
            print(f"ZIP file not found: {zip_path}", file=sys.stderr)
            return False
        if not zipfile.is_zipfile(zip_path):
            print(f"File is not a valid ZIP archive: {zip_path}", file=sys.stderr)
            return False
            
        extract_to_dir.mkdir(parents=True, exist_ok=True)
        print(f"Extracting {zip_path.name} to {extract_to_dir}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Log members being extracted (optional, can be verbose)
            # for member in zip_ref.namelist():
            # print(f"  Extracting: {member}")
            zip_ref.extractall(extract_to_dir)
        print("Extraction complete.")
        return True
    except zipfile.BadZipFile:
        print(f"Error: Invalid or corrupted ZIP file: {zip_path}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error extracting ZIP file {zip_path}: {e}", file=sys.stderr)
        return False

def prompt_user_for_confirmation(message: str) -> bool:
    """
    Asks the user a yes/no question on the command line.
    Returns: True for yes, False for no.
    """
    while True:
        reply = input(f"{message} (y/n): ").lower().strip()
        if reply == 'y' or reply == 'yes':
            return True
        if reply == 'n' or reply == 'no':
            return False
        print("Invalid input. Please enter 'y' or 'n'.")

# --- Placeholder for other core modules ---
# You would create similar files like toolchain.py, module_manager.py, etc.
# in the 'core' directory.