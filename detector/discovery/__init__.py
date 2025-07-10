# detector/discovery/__init__.py
import logging
from typing import List

from ..interfaces import Encoder, Discoverer
from .base import BaseDiscoverer
from .cpu import CpuDiscoverer
from .nvenc import NvencDiscoverer
from .vaapi import VaapiDiscoverer
from .qsv import QsvDiscoverer

class DiscoveryService:
    """
    Orchestrates multiple discovery strategies to find all potential encoders
    on the system.
    """
    def __init__(self):
        # The order here determines the fallback order if priorities are equal.
        self._discoverers: List[Discoverer] = [
            NvencDiscoverer(),
            VaapiDiscoverer(),
            QsvDiscoverer(),
            CpuDiscoverer(),  # The CPU is the ultimate fallback and should always be last.
        ]

    def discover_all(self) -> List[Encoder]:
        """
        Runs all registered discoverers and returns a flattened, sorted, and
        unique list of encoders.
        """
        all_encoders: List[Encoder] = []
        logging.info(f"Running {len(self._discoverers)} hardware discoverers...")
        for discoverer in self._discoverers:
            try:
                # Extend the list with encoders found by the current discoverer
                all_encoders.extend(discoverer.discover())
            except Exception as e:
                # We log the error but continue, so a failure in one discoverer
                # doesn't prevent others from running.
                logging.error(f"Error running {discoverer.__class__.__name__}: {e}")

        # De-duplicate by the user-facing device name. For encoders with the
        # same priority, the one that came last in all_encoders is kept.
        # We sort by priority reversed first to ensure this behavior.
        unique_encoders = {
            enc.device_name: enc
            for enc in sorted(all_encoders, key=lambda x: x.priority, reverse=True)
        }

        # Return the final list, sorted by priority (lower is better).
        return sorted(list(unique_encoders.values()), key=lambda x: x.priority)
