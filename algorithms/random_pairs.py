"""
Random pair selection algorithm.
"""

import random
import numpy as np
from typing import List, Tuple, Set
from .base import PairSelector


class RandomPairSelector(PairSelector):
    """
    Randomly selects pairs of images for comparison.

    Ensures no duplicate pairs are shown within a session.
    First N pairs are served from a fixed burn-in list (shuffled per session)
    if one is provided.
    """

    def __init__(self, image_ids: List[str], seed: int = None,
                 burn_in_pairs: List[Tuple[str, str]] = None, **kwargs):
        """
        Initialize the random pair selector.

        Args:
            image_ids: List of all available image IDs
            seed: Random seed for reproducibility (optional)
            burn_in_pairs: Fixed pairs for burn-in phase (shuffled per session)
        """
        super().__init__(image_ids, **kwargs)
        self.seed = seed
        if seed is not None:
            random.seed(seed)

        self.shown_pairs: Set[Tuple[str, str]] = set()

        # Build shuffled burn-in queue
        self._burn_in_queue: List[Tuple[str, str]] = []
        if burn_in_pairs:
            id_set = set(image_ids)
            self._burn_in_queue = [
                (a, b) for a, b in burn_in_pairs if a in id_set and b in id_set
            ]
            np.random.shuffle(self._burn_in_queue)
        self._burn_in_index = 0

    def _normalize_pair(self, img1: str, img2: str) -> Tuple[str, str]:
        """Normalize pair order for duplicate detection."""
        return tuple(sorted([img1, img2]))

    def get_next_pair(self) -> Tuple[str, str]:
        """
        Get the next pair of images. Serves from the fixed burn-in queue first,
        then falls back to random selection.

        Returns:
            Tuple of (image_id_1, image_id_2)

        Raises:
            ValueError: If no more unique pairs are available
        """
        # Serve fixed burn-in pairs first
        if self._burn_in_index < len(self._burn_in_queue):
            pair = self._burn_in_queue[self._burn_in_index]
            self._burn_in_index += 1
            self.shown_pairs.add(self._normalize_pair(*pair))
            return pair

        # Filter out excluded images
        available_images = [img for img in self.image_ids if img not in self.excluded_images]

        if len(available_images) < 2:
            raise ValueError("Not enough non-excluded images to select a pair")

        max_attempts = 1000
        attempts = 0

        while attempts < max_attempts:
            # Randomly select two different images from available pool
            img1, img2 = random.sample(available_images, 2)
            normalized = self._normalize_pair(img1, img2)

            if normalized not in self.shown_pairs:
                self.shown_pairs.add(normalized)
                return (img1, img2)

            attempts += 1

        raise ValueError("No more unique pairs available")

    def reset(self):
        """Reset the selector state."""
        super().reset()
        self.shown_pairs = set()
        if self.seed is not None:
            random.seed(self.seed)
