#!filepath: file_operations.py
import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import Optional

class CrossPlatformFileOps:
    """
    Handles all file system operations in a way that is compatible
    with Windows, macOS, and Linux.
    """
    def __init__(self):
        self.system = platform.system().lower()
        
    def get_temp_dir(self) -> str:
        """Gets the appropriate temporary directory for the OS."""
        return tempfile.gettempdir()
    
    def get_downloads_dir(self) -> str:
        """Gets the user's default Downloads directory in a cross-platform way."""
        home = Path.home()
        # This path construction works reliably on all major OSes.
        downloads_dir = home / "Downloads"
        
        # Ensure the directory exists, creating it if necessary.
        downloads_dir.mkdir(exist_ok=True)
        
        return str(downloads_dir)

    def get_main_download_dir(self) -> str:
        """
        Creates and returns the path to the main 'Adobe_Downloader' directory
        within the user's Downloads folder.
        """
        main_dir = os.path.join(self.get_downloads_dir(), "Adobe_Downloader")
        os.makedirs(main_dir, exist_ok=True)
        return main_dir
    
    def safe_filename(self, filename: str) -> str:
        """
        Creates a safe filename by removing or replacing characters that are
        invalid on the current operating system.
        """
        # Define characters that are invalid in filenames for each OS
        invalid_chars = {
            'windows': r'<>:"/\|?*',
            'darwin': r':/',
            'linux': r'/'
        }
        
        # Get the set of invalid characters for the current system, default to just '/'
        chars_to_remove = invalid_chars.get(self.system, '/')
        
        # Replace each invalid character with an underscore
        for char in chars_to_remove:
            filename = filename.replace(char, '_')
            
        # Limit filename length to a reasonable maximum (e.g., 200 characters)
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200 - len(ext)] + ext
            
        return filename
    
    def get_executable_path(self, executable: str) -> Optional[str]:
        """
        Finds the full path to an executable (like ffmpeg) in the system's PATH.
        Automatically adds '.exe' on Windows.
        """
        if self.system == 'windows' and not executable.endswith('.exe'):
            executable += '.exe'
            
        return shutil.which(executable)
