# detector/interfaces.py
from typing import Protocol, List, Optional
from dataclasses import dataclass

# Re-exporting from a central place for convenience
from .config import QualityProfile

# --- STEP 1: DEFINE CommandBuilder FIRST, AS Encoder WILL NEED IT ---
class CommandBuilder(Protocol):
    """Interface for any class that builds an FFmpeg command list."""
    def build_command(self, quality: QualityProfile) -> List[str]:
        ...

# --- STEP 2: MOVE THE Encoder DEFINITION HERE ---
# By defining Encoder here, we break the circular dependency.
@dataclass
class Encoder:
    """A template describing a potential encoder and how to use it."""
    name: str
    device_id: any
    device_name: str
    priority: int
    command_builder: CommandBuilder # This now correctly references the protocol above

# --- STEP 3: THE REMAINING PROTOCOLS CAN NOW USE Encoder ---
class Discoverer(Protocol):
    """Interface for any class that discovers a specific type of encoder."""
    def discover(self) -> List[Encoder]:
        ...

class Validator(Protocol):
    """Interface for any class that can validate an encoder."""
    async def validate(
        self, encoder: Encoder, original_video_path: str, converted_video_path: str, temp_output_path: str
    ) -> Optional[Encoder]:
        ...
