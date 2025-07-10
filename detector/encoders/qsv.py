# detector/encoders/qsv.py
from typing import List
from ..config import QualityProfile, QualityMapper

class QsvCommandBuilder:
    def build_command(self, quality: QualityProfile) -> List[str]:
        return ['-c:v', 'h264_qsv', '-preset', quality.value, '-global_quality', QualityMapper.get_crf(quality)]
