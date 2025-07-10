# detector/__init__.py

# Expose the main HardwareDetector class for easy importing
from .detector import HardwareDetector

# Expose key data classes and enums as well, using the correct path.
from .config import QualityProfile, ValidationConfig
# Import Encoder from its new, non-circular location
from .interfaces import Encoder
from .errors import HardwareDetectorError, HardwareDiscoveryError, EncoderValidationError
