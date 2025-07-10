#!filepath: progress_display.py
from tqdm import tqdm

class TqdmProgress:
    """
    A progress bar implementation using the excellent tqdm library.
    This provides a clean, well-formatted, and universally compatible
    progress bar for downloads, showing size, speed, and ETA.
    """
    def __init__(self, total_size: int, description: str):
        """
        Initializes the tqdm progress bar.
        
        Args:
            total_size (int): The total size of the download in bytes.
            description (str): A short description for the progress bar.
        """
        self.tqdm_bar = tqdm(
            total=total_size,
            unit='B',           # Use bytes as the unit
            unit_scale=True,    # Automatically convert to KB, MB, etc.
            unit_divisor=1024,
            desc=description,
            ncols=80,           # Set a reasonable width for most terminals
            leave=False         # Clear the bar on completion
        )

    def update(self, chunk_size: int):
        """
        Updates the progress bar by the given chunk size.
        
        Args:
            chunk_size (int): The number of bytes transferred in the last chunk.
        """
        self.tqdm_bar.update(chunk_size)

    def finish(self):
        """Closes and cleans up the progress bar."""
        self.tqdm_bar.close()
