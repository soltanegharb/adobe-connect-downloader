# detector/config.py
from enum import Enum
from dataclasses import dataclass

class QualityProfile(Enum):
    """Defines standard names for quality levels."""
    ULTRA, HIGH, MEDIUM, FAST, ULTRAFAST = "ultra", "high", "medium", "fast", "ultrafast"

@dataclass
class ValidationConfig:
    """Centralizes configuration to avoid magic numbers."""
    test_duration: int = 2  # Reduced from 5 to handle very short video segments
    timeout: int = 45
    cache_expiry_seconds: int = 3600
    video_hash_chunk_size: int = 4096

    # --- ADDED CONFIGURATION VALIDATION ---
    def __post_init__(self):
        """Validate configuration parameters after initialization."""
        if self.test_duration <= 0:
            raise ValueError("test_duration must be positive.")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive.")
        if self.cache_expiry_seconds < 0:
            raise ValueError("cache_expiry_seconds cannot be negative.")

class QualityMapper:
    """Centralizes quality profile to FFmpeg parameter mapping."""
    _CRF_MAP = {QualityProfile.ULTRA: '18', QualityProfile.HIGH: '21', QualityProfile.MEDIUM: '23', QualityProfile.FAST: '25', QualityProfile.ULTRAFAST: '27'}
    _PRESET_MAP_NVENC = {QualityProfile.ULTRA: 'p7', QualityProfile.HIGH: 'p6', QualityProfile.MEDIUM: 'p5', QualityProfile.FAST: 'p4', QualityProfile.ULTRAFAST: 'p1'}

    @staticmethod
    def get_crf(profile: QualityProfile) -> str:
        return QualityMapper._CRF_MAP[profile]

    @staticmethod
    def get_nvenc_preset(profile: QualityProfile) -> str:
        return QualityMapper._PRESET_MAP_NVENC[profile]
