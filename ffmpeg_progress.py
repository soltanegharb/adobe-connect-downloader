#!filepath: ffmpeg_progress.py
import subprocess
import re
import os
from tqdm import tqdm
from typing import Optional

class FFmpegWithProgress:
    """
    A class to run an FFmpeg command and display a tqdm progress bar.
    It works by running ffprobe to get the duration, then parsing the
    real-time output of ffmpeg to update the progress.
    """
    def __init__(self, command: list, ffmpeg_path: str, ffprobe_path: str):
        if not all([command, ffmpeg_path, ffprobe_path]):
            raise ValueError("Command, ffmpeg_path, and ffprobe_path must be provided.")
        self.command = command
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.duration_seconds = 0
        self.pbar = None

    def _get_duration(self) -> float:
        """Runs ffprobe to get the total duration of the input video."""
        try:
            # Find the primary input file from the command
            input_file = next((self.command[i+1] for i, v in enumerate(self.command) if v == '-i'), None)
            if not input_file:
                return 0.0

            probe_command = [
                self.ffprobe_path, '-v', 'error', '-show_entries',
                'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', input_file
            ]
            
            result = subprocess.run(probe_command, capture_output=True, text=True, check=True, env=os.environ)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
            print(f"Warning: Could not get video duration for progress bar. {e}")
            return 0.0

    def _parse_time(self, line: str) -> Optional[float]:
        """Parses the time from an FFmpeg output line."""
        time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})", line)
        if time_match:
            h, m, s, ms = map(int, time_match.groups())
            return h * 3600 + m * 60 + s + ms / 100.0
        return None

    def run(self) -> bool:
        """Executes the FFmpeg command and displays the progress bar."""
        self.duration_seconds = self._get_duration()
        
        # Use a generic spinner if duration is unknown, otherwise a full progress bar
        if self.duration_seconds > 0:
            self.pbar = tqdm(total=round(self.duration_seconds), unit='s', desc="Encoding", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
        else:
            print("Encoding video (duration unknown)...")

        process = subprocess.Popen(self.command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True, encoding="utf-8", errors="replace", env=os.environ)
        
        last_seconds = 0
        for line in process.stderr:
            current_seconds = self._parse_time(line)
            if current_seconds and self.pbar:
                update_amount = current_seconds - last_seconds
                if update_amount > 0:
                    self.pbar.update(round(update_amount, 2))
                    last_seconds = current_seconds
        
        if self.pbar:
            # Ensure the bar completes to 100% on success
            if process.wait() == 0:
                 self.pbar.update(self.duration_seconds - last_seconds)
            self.pbar.close()

        return process.returncode == 0
