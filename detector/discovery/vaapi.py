# detector/discovery/vaapi.py
import logging
import os
import shutil
from typing import List

from .base import BaseDiscoverer
from ..interfaces import Encoder
from ..encoders.vaapi import VaapiCommandBuilder
from ..errors import HardwareDiscoveryError

class VaapiDiscoverer(BaseDiscoverer):
    """Detects Video Acceleration API (VAAPI) devices in /dev/dri."""

    def discover(self) -> List[Encoder]:
        if self.system != 'linux' or not shutil.which('vainfo') or not os.path.exists('/dev/dri'):
            return []

        encoders: List[Encoder] = []
        try:
            render_nodes = sorted([d for d in os.listdir('/dev/dri') if d.startswith('renderD')])
            for dev_name in render_nodes:
                device_path = os.path.join('/dev/dri', dev_name)
                encoders.append(
                    Encoder(
                        name='h264_vaapi',
                        device_id=device_path,
                        device_name=f'VAAPI on {dev_name}',
                        priority=2,
                        command_builder=VaapiCommandBuilder(device_path=device_path)
                    )
                )
            logging.info(f"Discovered {len(encoders)} potential VAAPI device(s).")
            return encoders
        except Exception as e:
            raise HardwareDiscoveryError(f"An unexpected error occurred during VAAPI discovery: {e}") from e
