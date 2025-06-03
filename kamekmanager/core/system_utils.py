# kamekmanager/core/system_utils.py
import os
import sys
import ctypes
import pathlib
import subprocess
import shutil
import zipfile

from kamekmanager.common import constants 

# ... (all system_utils functions from Phase 1.4 - no changes here)
def check_admin_privileges() -> bool:
    if os.name == 'nt': 
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except AttributeError: 
             print("Could not determine admin status using ctypes.windll.shell32.IsUserAnAdmin().", file=sys.stderr)
             return False
        except Exception as e:
            print(f"Error checking admin privileges: {e}", file=sys.stderr)
            return False
    elif os.name == 'posix': 
        return os.geteuid() == 0
    else:
        print(f"Unsupported OS for admin check: {os.name}", file=sys.stderr)
        return False

def get_user_data_directory(tool_name: str = constants.APP_NAME) -> pathlib.Path:
    tool_name_fs = tool_name.replace(' ', '_') 
    if os.name == 'nt': 
        app_data_dir = os.getenv('APPDATA')
        if app_data_dir:
            path = pathlib.Path(app_data_dir) / tool_name_fs
        else:
            path = pathlib.Path.home() / f".{tool_name_fs}_config" 
    elif os.name == 'posix': 
        xdg_config_home = os.getenv('XDG_CONFIG_HOME')
        if xdg_config_home:
            path = pathlib.Path(xdg_config_home) / tool_name_fs
        else:
            path = pathlib.Path.home() / ".config" / tool_name_fs
    else:
        path = pathlib.Path.home() / f".{tool_name_fs}_config"
    
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating data directory {path}: {e}", file=sys.stderr)
    return path

def run_command(
    command_parts: list[str], 
    working_directory: str | os.PathLike | None = None, 
    capture_output: bool = True, 
    check_return_code: bool = True, 
    display_output_live: bool = False,
    env: dict | None = None 
) -> subprocess.CompletedProcess | None:
    try:
        command_str = ' '.join(str(part) for part in command_parts)
        if display_output_live:
            process = subprocess.Popen(command_parts, 
                                       cwd=working_directory,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, 
                                       text=True,
                                       bufsize=1, 
                                       universal_newlines=True,
                                       env=env)
            if process.stdout:
                for line in process.stdout:
                    print(line, end='') 
            process.wait() 
            result = subprocess.CompletedProcess(args=command_parts, 
                                                returncode=process.returncode,
                                                stdout=None, 
                                                stderr=None) 
        else:
            result = subprocess.run(
                command_parts,
                cwd=working_directory,
                capture_output=capture_output,
                text=True,
                check=False, 
                env=env
            )

        if check_return_code and result.returncode != 0:
            print(f"Command failed with exit code {result.returncode}: {command_str}", file=sys.stderr)
            if result.stdout and not display_output_live:
                print(f"STDOUT:\n{result.stdout}", file=sys.stderr)
            if result.stderr and not display_output_live: 
                print(f"STDERR:\n{result.stderr}", file=sys.stderr)
            return None 
        return result 
    except FileNotFoundError:
        print(f"Error: Command not found - {command_parts[0]}. Is it in PATH or an absolute path?", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An error occurred while running command {command_str}: {e}", file=sys.stderr)
        return None

def set_environment_variable(name: str, value: str, is_system_wide: bool = True) -> bool:
    if os.name == 'nt':
        if not check_admin_privileges() and is_system_wide:
            print(f"Admin privileges required to set system-wide environment variable '{name}'.", file=sys.stderr)
            return False
        quoted_value = f'"{value}"' if " " in value else value
        command = ['setx', name, quoted_value]
        if is_system_wide: command.append('/M')
        result = run_command(command, capture_output=True, check_return_code=False) 
        if result is not None:
            print(f"Environment variable '{name}' set. Restart shell/PC for changes.")
            return True
        else:
            print(f"Failed to execute setx command for '{name}'.", file=sys.stderr)
            return False
    else:
        print(f"Persistent env var setting not supported for {os.name}. Set '{name}' to '{value}' manually.", file=sys.stderr)
        return False

def get_environment_variable(name: str) -> str | None:
    return os.getenv(name)

def is_program_in_path(program_name: str) -> bool:
    return shutil.which(program_name) is not None

def add_directory_to_system_path(directory: str) -> bool:
    if os.name == 'nt':
        if not check_admin_privileges():
            print("Admin privileges required to modify system PATH.", file=sys.stderr)
            return False
        norm_directory = str(pathlib.Path(directory).resolve())
        print(f"WARNING: Modifying system PATH is risky. Ensure backups.")
        print(f"Attempting to add '{norm_directory}' to system PATH.")
        command = ['setx', 'PATH', f"%PATH%;{norm_directory}", '/M']
        result = run_command(command, capture_output=True, check_return_code=False)
        if result is not None:
            print(f"Directory '{norm_directory}' command to add to PATH executed. Restart shell/PC.")
            print("IMPORTANT: Verify PATH. `setx` can truncate it if too long.")
            return True
        else:
            print(f"Failed to execute command to add '{norm_directory}' to PATH.", file=sys.stderr)
            return False
    else:
        print("Automatic PATH modification not supported for this OS.", file=sys.stderr)
        return False

def download_file(url: str, destination_path: pathlib.Path, show_progress: bool = True) -> bool:
    try:
        import requests 
        print(f"Downloading {url} to {destination_path}...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, stream=True, timeout=60, headers=headers)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with open(destination_path, 'wb') as f:
            if show_progress and total_size > 0:
                downloaded_size = 0
                print(f"File size: {total_size / (1024*1024):.2f} MB")
                for chunk in response.iter_content(chunk_size=block_size):
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    progress = min(int(50 * downloaded_size / total_size), 50)
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
        print("The 'requests' library is required. `pip install requests`.", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}", file=sys.stderr)
        if destination_path.exists():
            try: destination_path.unlink()
            except OSError: pass
        return False
    except Exception as e:
        print(f"An unexpected error during download of {url}: {e}", file=sys.stderr)
        return False

def extract_zip(zip_path: pathlib.Path, extract_to_dir: pathlib.Path) -> bool:
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
    while True:
        reply = input(f"{message} (y/n): ").lower().strip()
        if reply in ['y', 'yes']: return True
        if reply in ['n', 'no']: return False
        print("Invalid input. Please enter 'y' or 'n'.")