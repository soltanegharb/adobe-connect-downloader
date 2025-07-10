# detector/discovery/nvenc.py
import logging
import shutil
from typing import List

from .base import BaseDiscoverer
from ..interfaces import Encoder
from ..encoders.nvenc import NvencCommandBuilder
from ..errors import HardwareDiscoveryError

class NvencDiscoverer(BaseDiscoverer):
    """Detects NVIDIA GPUs via nvidia-smi."""
    def discover(self) -> List[Encoder]:
        if self.system != 'linux' or not shutil.which('nvidia-smi'):
            return []

        encoders: List[Encoder] = []
        try:
            output = self.run_subprocess(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'])
            names = [name for name in output.strip().split('\n') if name]
            for i, name in enumerate(names):
                encoders.append(
                    Encoder(
                        name='h264_nvenc',
                        device_id=i,
                        device_name=f'NVENC on {name}',
                        priority=1,
                        command_builder=NvencCommandBuilder(device_index=i)
                    )
                )
            logging.info(f"Discovered {len(encoders)} potential NVENC device(s).")
            return encoders
        except HardwareDiscoveryError as e:
            logging.warning(f"Could not discover NVENC: {e}. Defaulting to one GPU as a fallback.")
            return [
                Encoder(
                    name='h264_nvenc',
                    device_id=0,
                    device_name='NVENC on GPU 0',
                    priority=1,
                    command_builder=NvencCommandBuilder(device_index=0)
                )
            ]
