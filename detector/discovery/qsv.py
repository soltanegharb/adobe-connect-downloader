# detector/discovery/qsv.py
import logging
import shutil
from typing import List

from .base import BaseDiscoverer
from ..interfaces import Encoder
from ..encoders.qsv import QsvCommandBuilder
from ..errors import HardwareDiscoveryError

class QsvDiscoverer(BaseDiscoverer):
    """Detects Intel Quick Sync Video (QSV) support."""

    def discover(self) -> List[Encoder]:
        if self.system != 'linux' or not shutil.which('lspci'):
            return []
        try:
            lspci_output = self.run_subprocess(['lspci']).lower()
            if 'vga compatible controller: intel corporation' in lspci_output:
                logging.info("Discovered Intel graphics, enabling QSV encoder.")
                return [
                    Encoder(
                        name='h264_qsv',
                        device_id='qsv',
                        device_name='Intel Quick Sync (QSV)',
                        priority=2,
                        command_builder=QsvCommandBuilder()
                    )
                ]
            return []
        except HardwareDiscoveryError as e:
            logging.warning(f"Could not check for QSV support, lspci command failed: {e}")
            return []
        except Exception as e:
            raise HardwareDiscoveryError(f"An unexpected error occurred during QSV discovery: {e}") from e
