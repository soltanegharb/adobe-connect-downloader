# detector/encoders/nvenc.py
from typing import List
from ..config import QualityProfile, QualityMapper

class NvencCommandBuilder:
    def __init__(self, device_index: int):
        self.device_index = device_index

    def build_command(self, quality: QualityProfile) -> List[str]:
        return ['-gpu', str(self.device_index), '-c:v', 'h264_nvenc', '-preset', QualityMapper.get_nvenc_preset(quality)]
