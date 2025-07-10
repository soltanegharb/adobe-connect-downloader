# detector/discovery/base.py
import logging, os, platform, shutil, subprocess
from typing import List
from ..interfaces import Encoder
from ..errors import HardwareDiscoveryError

class BaseDiscoverer:
    """Base class providing common utilities for discoverers."""
    def __init__(self):
        self.system = platform.system().lower()
    
    def run_subprocess(self, command: List[str]) -> str:
        try:
            kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE, 'text': True, 'encoding': 'utf-8', 'errors': 'replace'}
            result = subprocess.run(command, **kwargs, check=True)
            return result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise HardwareDiscoveryError(f"Command '{command[0]}' failed: {e}") from e
