"""
Utility-based recommender using learned preferences from BALD model.

Recommends images based on the utility scores learned through
pairwise comparisons with the PairwiseGP model.
"""

from typing import List, Dict, Any
from .base import Recommender


class UtilityRecommender(Recommender):
    """
    Recommender that uses utility scores from a BALD pair selector.

    Instead of using embedding similarity, this uses the learned
    utility function from pairwise comparison data.
    """

    def __init__(self, bald_selector=None, **kwargs):
        """
        Initialize the utility recommender.

        Args:
            bald_selector: BALDPairSelector instance with fitted model
        """
        super().__init__(**kwargs)
        self.bald_selector = bald_selector

    def generate_recommendations(
        self,
        chosen_images: List[str] = None,  # Not used - we use the model's utilities
        n_recommendations: int = 10,
        exclude_chosen: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on learned utility.

        Returns top 5 by utility plus images at 5th, 25th, 50th, 75th, 95th percentile.

        Args:
            chosen_images: Not used (kept for interface compatibility)
            n_recommendations: Number of recommendations to generate
            exclude_chosen: Whether to exclude images already shown in comparisons

        Returns:
            List of dicts with 'image_id', 'score' (utility), 'uncertainty', 'metadata', 'rank'
        """
        if self.bald_selector is None:
            return []

        # Get all images sorted by utility
        all_images = self.bald_selector.get_top_images(n=len(self.bald_selector.image_ids))

        # Get set of images that were in comparisons
        if exclude_chosen:
            compared_indices = set()
            for winner_idx, loser_idx in self.bald_selector.comparisons:
                compared_indices.add(winner_idx)
                compared_indices.add(loser_idx)
            compared_ids = {self.bald_selector.image_ids[idx] for idx in compared_indices}
        else:
            compared_ids = set()

        # Filter out compared images
        filtered_images = [
            (img_id, util, unc) for img_id, util, unc in all_images
            if not (exclude_chosen and img_id in compared_ids)
        ]

        if len(filtered_images) < n_recommendations:
            # Not enough images, return what we have
            return [
                {
                    'image_id': img_id,
                    'score': utility,
                    'uncertainty': uncertainty,
                    'metadata': {},
                    'rank': i + 1
                }
                for i, (img_id, utility, uncertainty) in enumerate(filtered_images[:n_recommendations])
            ]

        # Get top 5
        recommendations = []
        for img_id, utility, uncertainty in filtered_images[:5]:
            recommendations.append({
                'image_id': img_id,
                'score': utility,
                'uncertainty': uncertainty,
                'metadata': {},
                'rank': len(recommendations) + 1
            })

        # Get percentile samples from remaining images
        remaining = filtered_images[5:]
        if remaining:
            percentiles = [5, 25, 50, 75, 95]
            for p in percentiles:
                idx = int(len(remaining) * p / 100)
                idx = min(idx, len(remaining) - 1)
                img_id, utility, uncertainty = remaining[idx]
                recommendations.append({
                    'image_id': img_id,
                    'score': utility,
                    'uncertainty': uncertainty,
                    'metadata': {},
                    'rank': len(recommendations) + 1
                })
                if len(recommendations) >= n_recommendations:
                    break

        return recommendations[:n_recommendations]
