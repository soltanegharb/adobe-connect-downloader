# detector/encoders/vaapi.py
import logging, subprocess
from typing import List
from ..config import QualityProfile, QualityMapper

class VaapiCommandBuilder:
    def __init__(self, device_path: str):
        self.device_path = device_path

    def build_command(self, quality: QualityProfile) -> List[str]:
        qp = QualityMapper.get_crf(quality)
        # Add logic for older GPUs...
        return ['-vf', 'format=yuv420p,hwupload', '-c:v', 'h264_vaapi', '-profile:v', 'high', '-bf', '0', '-qp', qp]
