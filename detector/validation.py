# detector/validation.py
import asyncio
import logging
import os
from typing import Optional, Set

from .config import ValidationConfig, QualityProfile
from .interfaces import Encoder, Validator
from .errors import EncoderValidationError

class EncoderValidator(Validator):
    """
    Implements the Validator interface to perform FFmpeg validation for a
    single encoder, including a pre-flight check for support.
    """
    def __init__(self, config: ValidationConfig):
        self.config = config
        self._supported_ffmpeg_encoders: Optional[Set[str]] = None

    async def _is_encoder_supported(self, encoder_name: str) -> bool:
        """
        Checks if the given encoder name exists in the FFmpeg build.
        Caches the result to avoid repeated subprocess calls.
        """
        if self._supported_ffmpeg_encoders is None:
            logging.debug("Performing one-time check of available FFmpeg encoders...")
            self._supported_ffmpeg_encoders = set()
            try:
                proc = await asyncio.create_subprocess_exec(
                    'ffmpeg', '-hide_banner', '-encoders',
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                for line in stdout.decode('utf-8', errors='replace').splitlines():
                    if line.strip().startswith('V') and '264' in line: # Video encoders for H.264
                        parts = line.strip().split()
                        if len(parts) > 1:
                            self._supported_ffmpeg_encoders.add(parts[1])
            except Exception as e:
                logging.error(f"Failed to get list of FFmpeg encoders: {e}")
                return False
            logging.debug(f"Found supported encoders: {self._supported_ffmpeg_encoders}")

        return encoder_name in self._supported_ffmpeg_encoders

    async def validate(
        self, encoder: Encoder, original_video_path: str, converted_video_path: str, temp_output_path: str
    ) -> Optional[Encoder]:
        """Asynchronously validates a single encoder, with fallback logic."""
        if not await self._is_encoder_supported(encoder.name):
            logging.debug(f"Skipping '{encoder.device_name}' because encoder '{encoder.name}' is not supported by this FFmpeg build.")
            return None

        test_cmd_args = encoder.command_builder.build_command(QualityProfile.MEDIUM)
        
        try:
            if await self._run_ffmpeg_test(encoder, original_video_path, test_cmd_args, temp_output_path):
                logging.info(f"✓ VALID: '{encoder.device_name}' works with the original video.")
                return encoder

            if os.path.exists(converted_video_path):
                logging.debug(f"Retrying '{encoder.device_name}' with pre-converted input...")
                if await self._run_ffmpeg_test(encoder, converted_video_path, test_cmd_args, temp_output_path):
                    logging.info(f"✓ VALID: '{encoder.device_name}' works with the pre-converted video.")
                    return encoder
        except EncoderValidationError as e:
            logging.warning(f"✗ FAILED: {e}")
        except Exception as e:
            logging.error(f"An unexpected exception occurred during validation of '{encoder.device_name}': {e}")
            
        return None

    async def _run_ffmpeg_test(
        self, encoder: Encoder, video_path: str, test_args: list, output_path: str
    ) -> bool:
        command = ['ffmpeg', '-y', '-loglevel', 'error']
        if encoder.name == 'h264_vaapi':
            command.extend(['-hwaccel', 'vaapi', '-vaapi_device', encoder.device_id])
        command.extend(['-i', video_path, '-t', str(self.config.test_duration)])
        command.extend(['-map', '0:v'])
        command.extend(test_args)
        command.append(output_path)
        
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            # Use wait_for on communicate() to handle timeout
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.config.timeout)
            
            if proc.returncode == 0:
                return True
            else:
                error_output = stderr.decode('utf-8', errors='replace').strip().split('\n')[-1]
                raise EncoderValidationError(f"'{encoder.device_name}' on '{os.path.basename(video_path)}'. Error: {error_output}")
        except asyncio.TimeoutError:
            raise EncoderValidationError(f"'{encoder.device_name}' timed out after {self.config.timeout}s.") from None
        finally:
            # --- ROBUSTNESS FIX: Ensure the process is always terminated ---
            if proc and proc.returncode is None:
                logging.debug(f"Forcefully terminating hung validation process for '{encoder.device_name}' (PID: {proc.pid})")
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except Exception as e:
                    logging.warning(f"Error during cleanup of process {proc.pid}: {e}. Attempting kill.")
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass # Process already died
