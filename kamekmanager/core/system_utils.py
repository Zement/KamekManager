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

from kamekmanager.common import constants # Assuming constants.py is in a sibling 'common' directory

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
        except Exception:
            print("Error checking admin privileges.", file=sys.stderr)
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
            path = pathlib.Path.home() / f".{tool_name}" 
    elif os.name == 'posix': # Linux/macOS
        # Typically ~/.config/ToolName or ~/.local/share/ToolName
        # Using ~/.ToolName for simplicity for now, can be refined.
        path = pathlib.Path.home() / f".{tool_name}"
    else:
        # Fallback for other OSes
        path = pathlib.Path.home() / f".{tool_name}"
    
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating data directory {path}: {e}", file=sys.stderr)
        # Depending on how critical this is, you might want to raise the exception
        # or return a default path / handle it gracefully.
    return path

def run_command(
    command_parts: list[str], 
    working_directory: str | os.PathLike | None = None, 
    capture_output: bool = True, 
    check_return_code: bool = True,
    display_output_live: bool = False # New parameter
    # request_admin: bool = False # Complex to implement robustly, deferring
) -> subprocess.CompletedProcess | None:
    """
    A wrapper around subprocess.run() to execute external commands.
    
    Args:
        command_parts: List of strings forming the command and its arguments.
        working_directory: The directory from which to run the command.
        capture_output: If True, stdout and stderr are captured.
        check_return_code: If True, raises CalledProcessError for non-zero exit codes.
        display_output_live: If True, prints stdout/stderr as it's generated.
                             capture_output should ideally be False if this is True,
                             or handle both carefully.

    Returns:
        subprocess.CompletedProcess object or None on failure if not raising an exception.
    """
    try:
        print(f"Running command: {' '.join(command_parts)}")
        if working_directory:
            print(f"In directory: {working_directory}")

        if display_output_live:
            # This streams output directly.
            # For more control (e.g., capturing and displaying), it's more complex.
            process = subprocess.Popen(command_parts, 
                                       cwd=working_directory,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, # Combine stdout and stderr
                                       text=True,
                                       bufsize=1, # Line buffered
                                       universal_newlines=True)
            if process.stdout:
                for line in process.stdout:
                    print(line, end='')
            process.wait() # Wait for the process to complete
            # Create a CompletedProcess-like object for consistency
            # Note: This is a simplified version. `process.returncode` is key.
            result = subprocess.CompletedProcess(args=command_parts, 
                                                returncode=process.returncode,
                                                stdout=None, # Output was already printed
                                                stderr=None) 
        else:
            result = subprocess.run(
                command_parts,
                cwd=working_directory,
                capture_output=capture_output,
                text=True,  # Decodes stdout/stderr as text
                check=False # We'll check the return code manually if needed
            )

        if check_return_code and result.returncode != 0:
            print(f"Command failed with exit code {result.returncode}: {' '.join(command_parts)}", file=sys.stderr)
            if capture_output and not display_output_live: # Only print if not already displayed
                if result.stdout:
                    print(f"STDOUT:\n{result.stdout}", file=sys.stderr)
                if result.stderr:
                    print(f"STDERR:\n{result.stderr}", file=sys.stderr)
            # Consider raising subprocess.CalledProcessError(result.returncode, command_parts, output=result.stdout, stderr=result.stderr)
            return None # Or raise
        return result
    except FileNotFoundError:
        print(f"Error: Command not found - {command_parts[0]}. Is it in PATH?", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An error occurred while running command {' '.join(command_parts)}: {e}", file=sys.stderr)
        return None

def set_environment_variable(name: str, value: str, is_system_wide: bool = True) -> bool:
    """
    Persistently sets an environment variable (Windows specific using setx).
    WARNING: On Windows, `setx` has a 1024 char limit for the combined PATH.
             Modifying PATH programmatically is risky and should be done with extreme care.
             Consider warning users or providing manual instructions for PATH.
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
        
        command = ['setx', name, value]
        if is_system_wide:
            command.append('/M')
        
        print(f"Attempting to set environment variable: {' '.join(command)}")
        result = run_command(command, capture_output=True, check_return_code=False)
        if result and result.returncode == 0:
            print(f"Environment variable '{name}' set successfully. You may need to restart your shell or PC for changes to take effect.")
            return True
        else:
            print(f"Failed to set environment variable '{name}'.", file=sys.stderr)
            if result and result.stdout: print(f"Output: {result.stdout}", file=sys.stderr)
            if result and result.stderr: print(f"Error: {result.stderr}", file=sys.stderr)
            return False
    else:
        print(f"Setting persistent environment variables programmatically is not directly supported for {os.name} in this script.", file=sys.stderr)
        print(f"Please set '{name}' to '{value}' manually in your shell configuration (e.g., .bashrc, .zshrc).", file=sys.stderr)
        return False # Or indicate partial success/manual step needed

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
             This function is provided as a starting point but use with extreme caution.
    Returns: True on success, False otherwise.
    """
    if os.name == 'nt':
        if not check_admin_privileges():
            print("Admin privileges required to modify system PATH.", file=sys.stderr)
            return False

        current_path = get_environment_variable("PATH")
        if current_path is None:
            print("Could not retrieve current PATH.", file=sys.stderr)
            return False

        # Normalize directory path
        norm_directory = str(pathlib.Path(directory).resolve())

        if norm_directory in current_path.split(os.pathsep):
            print(f"Directory '{norm_directory}' is already in PATH.")
            return True
        
        # Construct the new PATH. It's crucial to get the *current system* PATH,
        # not just the one from os.getenv which might be user-specific or process-specific.
        # This is hard to do reliably without direct registry access or more complex calls.
        # `setx PATH "%PATH%;new_directory"` is a common way but relies on `setx` expanding %PATH% correctly.
        
        print(f"WARNING: Modifying system PATH is risky. Ensure backups or manual restoration capability.")
        print(f"Attempting to add '{norm_directory}' to PATH.")
        
        # The safest way with setx is to provide the *entire new path string*.
        # However, getting the true system PATH to append to is non-trivial.
        # A common but risky approach:
        # new_path_value = f"{current_path}{os.pathsep}{norm_directory}" 
        # This assumes current_path from os.getenv IS the full system path if running as admin.

        # A slightly more robust way to get system path for `setx /M` is to query it first.
        # This requires parsing `reg query` output or similar, which is getting complex.
        # For now, let's demonstrate the direct `setx PATH "%PATH%;<new_dir>"` approach,
        # but highlight its limitations.
        
        # Command to append using setx's own %PATH% expansion (for system path if /M is used)
        # This is generally how it's done, but `setx` itself has the 1024 char limit.
        command = ['setx', 'PATH', f"%PATH%;{norm_directory}", '/M']
        
        result = run_command(command, capture_output=True, check_return_code=False)
        if result and result.returncode == 0:
            print(f"Directory '{norm_directory}' added to PATH. Restart your shell or PC.")
            print("IMPORTANT: Verify your PATH variable. `setx` can truncate it if it's too long.")
            return True
        else:
            print(f"Failed to add '{norm_directory}' to PATH.", file=sys.stderr)
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
    # Placeholder: Implementation requires 'requests' library.
    # pip install requests
    try:
        import requests # Moved import here to avoid hard dependency if not used
        print(f"Downloading {url} to {destination_path}...")
        response = requests.get(url, stream=True, timeout=30) # Added timeout
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192 # 8KB
        
        # Ensure parent directory exists
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        with open(destination_path, 'wb') as f:
            if show_progress and total_size > 0:
                # Basic progress bar
                downloaded_size = 0
                for chunk in response.iter_content(chunk_size=block_size):
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    progress = int(50 * downloaded_size / total_size)
                    sys.stdout.write(f"\r[{'#' * progress}{'.' * (50 - progress)}] {downloaded_size / (1024*1024):.2f}MB / {total_size / (1024*1024):.2f}MB")
                    sys.stdout.flush()
                sys.stdout.write('\n')
            else:
                for chunk in response.iter_content(chunk_size=block_size):
                    f.write(chunk)
        print("Download complete.")
        return True
    except ImportError:
        print("The 'requests' library is required for downloading. Please install it (`pip install requests`).", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}", file=sys.stderr)
        if destination_path.exists(): # Clean up partial download
            try:
                destination_path.unlink()
            except OSError:
                pass # Ignore if cleanup fails
        return False
    except Exception as e:
        print(f"An unexpected error occurred during download: {e}", file=sys.stderr)
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
        
        extract_to_dir.mkdir(parents=True, exist_ok=True)
        print(f"Extracting {zip_path} to {extract_to_dir}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
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
        if reply[:1] == 'y':
            return True
        if reply[:1] == 'n':
            return False
        print("Invalid input. Please enter 'y' or 'n'.")

# --- Placeholder for other core modules ---
# You would create similar files like python_env.py, toolchain.py, etc.
# in the 'core' directory.