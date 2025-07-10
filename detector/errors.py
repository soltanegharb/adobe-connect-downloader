# detector/errors.py

class HardwareDetectorError(Exception):
    """Base exception for all errors in this package."""
    pass

class HardwareDiscoveryError(HardwareDetectorError):
    """Raised when there's an error probing the system for hardware."""
    pass

class EncoderValidationError(HardwareDetectorError):
    """Raised when an encoder fails the validation process."""
    pass
