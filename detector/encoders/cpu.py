# detector/encoders/cpu.py
from typing import List
from ..config import QualityProfile, QualityMapper

class CpuCommandBuilder:
    def build_command(self, quality: QualityProfile) -> List[str]:
        return ['-c:v', 'libx264', '-preset', quality.value, '-crf', QualityMapper.get_crf(quality)]
