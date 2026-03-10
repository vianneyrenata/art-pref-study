"""
Base classes for modular algorithms.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any


class PairSelector(ABC):
    """
    Base class for pair selection algorithms.

    Subclasses should implement get_next_pair() to return the next
    pair of images to compare based on their specific strategy.
    """

    def __init__(self, image_ids: List[str], excluded_images: List[str] = None, **kwargs):
        """
        Initialize the pair selector.

        Args:
            image_ids: List of all available image IDs
            excluded_images: List of image IDs to exclude from selection (e.g., practice trial images)
            **kwargs: Algorithm-specific parameters
        """
        self.image_ids = image_ids
        self.excluded_images = set(excluded_images or [])

    @abstractmethod
    def get_next_pair(self) -> Tuple[str, str]:
        """
        Get the next pair of images to compare.

        Returns:
            Tuple of (image_id_1, image_id_2)
        """
        pass

    def record_comparison(self, image_1: str, image_2: str, chosen: str):
        """
        Record the result of a comparison.

        Args:
            image_1: First image ID
            image_2: Second image ID
            chosen: The chosen image ID
        """
        pass

    def reset(self):
        """Reset the selector state."""
        pass


class Recommender(ABC):
    """
    Base class for recommendation algorithms.

    Subclasses should implement generate_recommendations() to return
    recommended images based on user preferences.
    """

    def __init__(self, **kwargs):
        """
        Initialize the recommender.

        Args:
            **kwargs: Algorithm-specific parameters
        """
        pass

    @abstractmethod
    def generate_recommendations(
        self,
        chosen_images: List[str],
        n_recommendations: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on chosen images.

        Args:
            chosen_images: List of image IDs the user preferred
            n_recommendations: Number of recommendations to generate

        Returns:
            List of dicts with 'image_id', 'score', and optional metadata
        """
        pass
