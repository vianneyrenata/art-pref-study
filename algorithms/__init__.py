"""
Modular algorithms for the experiment platform.

Pair Selection Algorithms:
- RandomPairSelector: Random pair selection
- BALDPairSelector: BoTorch-based active learning with uncertainty tracking

Recommender Algorithms:
- EmbeddingRecommender: RAG-based using CLIP embeddings
- UtilityRecommender: Uses learned utility from BALD model
"""

from .base import PairSelector, Recommender
from .random_pairs import RandomPairSelector
from .recommender import EmbeddingRecommender

# Conditional imports for BoTorch-based algorithms
try:
    from .bald_selector import BALDPairSelector
    from .utility_recommender import UtilityRecommender
    BALD_AVAILABLE = True
except ImportError as e:
    BALDPairSelector = None
    UtilityRecommender = None
    BALD_AVAILABLE = False
    print(f"Warning: BoTorch algorithms not available: {e}")

__all__ = [
    'PairSelector',
    'Recommender',
    'RandomPairSelector',
    'EmbeddingRecommender',
    'BALDPairSelector',
    'UtilityRecommender',
    'BALD_AVAILABLE',
]
