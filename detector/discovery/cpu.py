# detector/discovery/cpu.py
from typing import List
from .base import BaseDiscoverer
from ..interfaces import Encoder
from ..encoders.cpu import CpuCommandBuilder

class CpuDiscoverer(BaseDiscoverer):
    def discover(self) -> List[Encoder]:
        """Returns the CPU encoder as a guaranteed fallback."""
        return [
            Encoder(
                name='libx264',
                device_id='cpu',
                device_name='CPU (libx264)',
                priority=10,
                command_builder=CpuCommandBuilder()
            )
        ]
