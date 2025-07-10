# detector/caching.py
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Optional

from .config import ValidationConfig
from .encoders import Encoder

@dataclass
class CacheEntry:
    """Holds cached encoder data and its timestamp."""
    encoders: List[Encoder]
    timestamp: float

class EncoderCache:
    """Handles storing, retrieving, and expiring cached encoder lists."""
    def __init__(self, config: ValidationConfig):
        self.config = config
        self._cache: Dict[str, CacheEntry] = {}

    def get_video_hash(self, video_file_path: str) -> Optional[str]:
        """Generates a stable hash for a video file."""
        try:
            hasher = hashlib.sha256()
            with open(video_file_path, 'rb') as f:
                for _ in range(64):  # Read first ~256KB for performance
                    chunk = f.read(self.config.video_hash_chunk_size)
                    if not chunk: break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except FileNotFoundError:
            logging.error(f"Cannot generate hash, file not found: {video_file_path}")
            return None
            
    def get(self, video_hash: str) -> Optional[List[Encoder]]:
        """Retrieves an encoder list from the cache if it's valid and not expired."""
        if video_hash in self._cache:
            entry = self._cache[video_hash]
            if (time.time() - entry.timestamp) < self.config.cache_expiry_seconds:
                logging.info(f"Returning cached encoder list for video hash: {video_hash[:8]}...")
                return entry.encoders
            else:
                logging.info("Cache entry expired.")
                del self._cache[video_hash]
        return None

    def set(self, video_hash: str, encoders: List[Encoder]):
        """Adds a new entry to the cache."""
        logging.info(f"Caching successful validation result for hash: {video_hash[:8]}...")
        self._cache[video_hash] = CacheEntry(encoders=encoders, timestamp=time.time())
