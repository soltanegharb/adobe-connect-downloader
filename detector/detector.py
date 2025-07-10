# detector/detector.py
import asyncio
import logging
import os
import tempfile
import subprocess
from contextlib import asynccontextmanager # --- USE ASYNC-AWARE CONTEXT MANAGER ---
from typing import List, Optional

from .config import ValidationConfig
from .caching import EncoderCache
from .discovery import DiscoveryService
from .validation import EncoderValidator
from .interfaces import Encoder

# --- CONVERTED TO ASYNC CONTEXT MANAGER ---
@asynccontextmanager
async def temp_files(*filenames):
    """An async context manager to ensure temporary files are deleted."""
    try:
        yield
    finally:
        for f in filenames:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError as e:
                    logging.error(f"Error removing temporary file {f}: {e}")

class HardwareDetector:
    """
    Orchestrates the discovery and asynchronous validation of hardware encoders.
    """
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        self.cache = EncoderCache(self.config)
        self.discovery = DiscoveryService()
        self.validator = EncoderValidator(self.config)

    async def find_and_validate_functional_encoders(self, video_file_path: str) -> List[Encoder]:
        """Finds all functional encoders for a given video file, using a cache."""
        video_hash = self.cache.get_video_hash(video_file_path)
        if video_hash:
            cached_encoders = self.cache.get(video_hash)
            if cached_encoders is not None:
                return cached_encoders

        logging.info("Starting fresh hardware validation...")
        potential_encoders = self.discovery.discover_all()

        temp_dir = tempfile.gettempdir()
        os.makedirs(temp_dir, exist_ok=True)
        temp_output_base = os.path.join(temp_dir, 'test_encode')
        temp_converted = os.path.join(temp_dir, 'test_converted.mkv')

        # --- USE ASYNC WITH ---
        async with temp_files(temp_converted):
            await self._pre_convert_for_fallback(video_file_path, temp_converted)

            tasks = []
            temp_task_files = [f"{temp_output_base}_{i}.mkv" for i in range(len(potential_encoders))]

            # --- USE ASYNC WITH ---
            async with temp_files(*temp_task_files):
                for i, encoder in enumerate(potential_encoders):
                    task = self.validator.validate(
                        encoder, video_file_path, temp_converted, temp_task_files[i]
                    )
                    tasks.append(task)
                results = await asyncio.gather(*tasks)

        functional_encoders = sorted([res for res in results if res is not None], key=lambda enc: enc.priority)

        if not functional_encoders:
            logging.critical("CRITICAL: No functional encoders could be validated.")
        elif video_hash:
            self.cache.set(video_hash, functional_encoders)

        return functional_encoders

    async def _pre_convert_for_fallback(self, source_path: str, dest_path: str):
        """Creates a standardized video file to use as a fallback during validation."""
        logging.info("Pre-converting video for fallback testing...")
        command = [
            'ffmpeg', '-y', '-loglevel', 'error', '-i', source_path,
            '-t', str(self.config.test_duration), '-c:v', 'libx264',
            '-profile:v', 'high', '-vf', 'format=yuv420p', '-an', dest_path
        ]
        try:
            # Run the synchronous command in an async executor to not block the event loop
            proc = await asyncio.create_subprocess_exec(*command)
            await asyncio.wait_for(proc.wait(), timeout=self.config.timeout)
            if proc.returncode != 0:
                logging.warning("Pre-conversion command failed.")
        except Exception as e:
            logging.warning(f"Could not pre-convert video for fallback. Error: {e}")
