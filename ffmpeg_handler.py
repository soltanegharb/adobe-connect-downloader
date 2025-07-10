#!filepath: ffmpeg_handler.py
import os
import subprocess
import logging
import platform
import shutil
import asyncio
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass

# Local imports with corrected paths for the modular structure
from detector import HardwareDetector, QualityProfile, Encoder, config
from ffmpeg_progress import FFmpegWithProgress

@dataclass
class NormalizedMedia:
    """Holds paths to the standardized intermediate media files."""
    video_path: str
    audio_path: str

class FFmpegHandler:
    """
    Manages a robust two-pass FFmpeg workflow to fix A/V sync issues.
    Pass 1: Normalizes video and audio streams into clean, standard-compliant files, using GPU acceleration.
    Pass 2: Merges the clean files using hardware acceleration.
    """
    def __init__(self):
        # Set environment variables for improved AMD GPU stability on Linux
        if platform.system().lower() == 'linux':
            logging.debug("Setting Linux-specific environment variables for AMD VAAPI.")
            os.environ['LIBVA_DRIVER_NAME'] = 'radeonsi'
            os.environ['allow_rgb10_configs'] = 'false'

        self.hardware = HardwareDetector()
        self.ffmpeg_path = self._find_executable('ffmpeg')
        self.ffprobe_path = self._find_executable('ffprobe')
        if not (self.ffmpeg_path and self.ffprobe_path):
            raise FileNotFoundError("FFmpeg or ffprobe not found. Please install FFmpeg suite and ensure it's in your system's PATH.")

    def _find_executable(self, name: str) -> Optional[str]:
        path = shutil.which(name)
        if path:
            logging.info(f"Found {name} at: {path}")
            return path
        logging.error(f"{name} not found in system PATH.")
        return None

    def _run_ffmpeg_command(self, command: List[str], desc: str) -> bool:
        """A helper to run a quiet FFmpeg command and check for errors."""
        logging.info(f"Executing FFmpeg pass: {desc}")
        logging.debug(f"FFmpeg command: {' '.join(command)}")
        try:
            kwargs = {'check': True, 'capture_output': True, 'text': True, 'encoding': 'utf-8', 'errors': 'replace', 'env': os.environ}
            if platform.system().lower() == 'windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(command, timeout=3600, **kwargs) # 60 min timeout for safety
            if result.stderr:
                logging.debug(f"FFmpeg output for '{desc}':\n{result.stderr}")
            return True
        except subprocess.CalledProcessError as e:
            logging.critical(f"FFmpeg pass '{desc}' failed with exit code {e.returncode}.")
            error_lines = e.stderr.strip().split('\n')
            logging.error("Last 5 lines of FFmpeg error output:")
            for line in error_lines[-5:]:
                logging.error(f"  {line}")
            return False
        except Exception as e:
            logging.critical(f"An unexpected error occurred during FFmpeg pass '{desc}': {e}")
            return False

    def normalize_video_stream(self, video_files: List[str], output_path: str, quality: QualityProfile) -> bool:
        """
        Pass 1.1: Takes raw video files, joins them, and normalizes to a standard
        30fps H.264 stream in MKV, prioritizing GPU acceleration with a CPU fallback.
        """
        if not video_files:
            logging.error("No video files provided for normalization.")
            return False

        logging.info("--- Pass 1.1: Normalizing Video Stream (Hardware Accelerated) ---")
        
        functional_encoders = asyncio.run(self.hardware.find_and_validate_functional_encoders(video_files[0]))

        use_gpu = False
        hwaccel_args = []
        
        if functional_encoders:
            best_encoder = functional_encoders[0]
            encoder_args = best_encoder.command_builder.build_command(quality)
            encoder_name = best_encoder.device_name
            use_gpu = best_encoder.name != 'libx264'
            logging.info(f"Selected validated encoder for video normalization: {encoder_name}")
            
            if use_gpu and best_encoder.name == 'h264_vaapi':
                hwaccel_args = ['-hwaccel', 'vaapi', '-vaapi_device', best_encoder.device_id, '-hwaccel_output_format', 'vaapi']
        else:
            logging.warning("All encoders failed validation, likely due to a corrupted source file.")
            logging.warning("Attempting a robust, non-validated CPU-only normalization as a last resort.")
            encoder_name = f"libx264 (CPU - Fallback Mode)"
            encoder_args = ['-c:v', 'libx264', '-preset', quality.value, '-crf', config.QualityMapper.get_crf(quality)]

        command = [self.ffmpeg_path, '-y', '-hide_banner']
        command.extend(['-c:v', 'vp6f'])
        command.extend(hwaccel_args)

        for file_path in video_files:
            command.extend(['-i', file_path])

        if len(video_files) == 1:
            filter_graph = "[0:v]fps=30[outv]" if not use_gpu else "[0:v]fps=30,hwupload[outv]"
        else:
            filter_inputs = ''.join([f'[{i}:v]' for i in range(len(video_files))])
            gpu_filter_chain = ",hwupload" if use_gpu else ""
            filter_graph = (
                f"{filter_inputs}concat=n={len(video_files)}:v=1:a=0[concat_out];"
                f"[concat_out]fps=30{gpu_filter_chain}[outv]"
            )

        command.extend(['-filter_complex', filter_graph, '-map', '[outv]'])
        command.extend(encoder_args)
        command.append(output_path)

        return self._run_ffmpeg_command(command, f"Video Normalization with {encoder_name}")

    def normalize_audio_stream(self, audio_files: List[str], output_path: str) -> bool:
        """
        Pass 1.2: Takes raw audio files, joins them, and normalizes to a standard
        44.1kHz AAC stream, resetting timestamps to fix initial delay issues.
        """
        if not audio_files:
            logging.error("No audio files provided for normalization.")
            return False

        logging.info("--- Pass 1.2: Normalizing Audio Stream ---")
        command = [self.ffmpeg_path, '-y', '-hide_banner']

        for file_path in audio_files:
            command.extend(['-i', file_path])

        audio_filters = "aresample=44100,asetpts=PTS-STARTPTS"

        if len(audio_files) == 1:
            filter_graph = f"[0:a]{audio_filters}[outa]"
        else:
            filter_inputs = ''.join([f'[{i}:a]' for i in range(len(audio_files))])
            filter_graph = f"{filter_inputs}concat=n={len(audio_files)}:v=0:a=1[concat_out];[concat_out]{audio_filters}[outa]"

        command.extend(['-filter_complex', filter_graph, '-map', '[outa]'])
        command.extend(['-c:a', 'aac', '-b:a', '192k'])
        command.append(output_path)

        return self._run_ffmpeg_command(command, "Audio Normalization")

    def merge_normalized_streams(self, media: NormalizedMedia, output_file: str, quality: QualityProfile) -> bool:
        """
        Pass 2: Merges the clean, normalized video and audio files into the final
        MP4, using the best available hardware encoder for speed.
        """
        logging.info("--- Pass 2: Final Hardware-Accelerated Merge ---")
        functional_encoders = asyncio.run(self.hardware.find_and_validate_functional_encoders(media.video_path))
        if not functional_encoders:
            logging.critical("Validation failed: No functional encoders (GPU or CPU) found for the normalized video file.")
            return False

        best_encoder = functional_encoders[0]
        logging.info(f"Selected best validated encoder for final merge: '{best_encoder.device_name}'")

        command = [self.ffmpeg_path, '-y', '-hide_banner']
        command.extend(['-i', media.video_path, '-i', media.audio_path])

        encoder_args = best_encoder.command_builder.build_command(quality)
        command.extend(encoder_args)
        
        # --- FINAL A/V SYNC FIX ---
        # Instead of just copying the audio stream (-c:a copy), we re-encode it.
        # This forces FFmpeg to create a brand new audio stream that is perfectly
        # synchronized to the video's timestamps, fixing any lingering drift.
        command.extend(['-c:a', 'aac', '-b:a', '192k'])
        
        command.extend(['-movflags', '+faststart'])
        command.append(output_file)

        progress_runner = FFmpegWithProgress(command, self.ffmpeg_path, self.ffprobe_path)
        return progress_runner.run()
