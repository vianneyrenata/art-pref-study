"""
Embedding-based recommendation algorithm using ChromaDB.
"""

import numpy as np
from typing import List, Dict, Any
import chromadb
from .base import Recommender


class EmbeddingRecommender(Recommender):
    """
    RAG-based recommender using CLIP embeddings from ChromaDB.

    Computes average embedding of chosen images and finds
    most similar images in the database.
    """

    def __init__(
        self,
        db_path: str,
        collection_name: str = "sample-mini",
        **kwargs
    ):
        """
        Initialize the embedding recommender.

        Args:
            db_path: Path to ChromaDB database
            collection_name: Name of the collection to query
        """
        super().__init__(**kwargs)
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_collection(name=collection_name)

    def generate_recommendations(
        self,
        chosen_images: List[str],
        n_recommendations: int = 10,
        exclude_chosen: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on chosen images.

        Returns top 5 by similarity plus images at 5th, 25th, 50th, 75th, 95th percentile.

        Args:
            chosen_images: List of image IDs the user preferred
            n_recommendations: Number of recommendations to generate
            exclude_chosen: Whether to exclude already-chosen images

        Returns:
            List of dicts with 'image_id', 'score', 'metadata'
        """
        if not chosen_images:
            return []

        # Deduplicate chosen images
        unique_chosen = list(set(chosen_images))

        # Get embeddings for chosen images
        results = self.collection.get(
            ids=unique_chosen,
            include=['embeddings']
        )

        if results['embeddings'] is None or len(results['embeddings']) == 0:
            return []

        # Calculate average embedding
        embeddings = np.array(results['embeddings'])
        avg_embedding = np.mean(embeddings, axis=0)

        # L2 normalize
        avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)

        # Query for ALL images to get full distribution
        total_images = self.collection.count()
        query_results = self.collection.query(
            query_embeddings=[avg_embedding.tolist()],
            n_results=total_images,
            include=['metadatas', 'distances']
        )

        # Build list of all results with similarity scores
        all_results = []
        for img_id, distance, metadata in zip(
            query_results['ids'][0],
            query_results['distances'][0],
            query_results['metadatas'][0]
        ):
            if exclude_chosen and img_id in unique_chosen:
                continue
            similarity = 1 / (1 + distance)
            all_results.append({
                'image_id': img_id,
                'score': similarity,
                'metadata': metadata
            })

        if len(all_results) < n_recommendations:
            # Return what we have
            for i, rec in enumerate(all_results):
                rec['rank'] = i + 1
            return all_results[:n_recommendations]

        # Get top 5
        recommendations = all_results[:5]

        # Get percentile samples from remaining
        remaining = all_results[5:]
        if remaining:
            percentiles = [5, 25, 50, 75, 95]
            for p in percentiles:
                idx = int(len(remaining) * p / 100)
                idx = min(idx, len(remaining) - 1)
                recommendations.append(remaining[idx])
                if len(recommendations) >= n_recommendations:
                    break

        # Add ranks
        for i, rec in enumerate(recommendations[:n_recommendations]):
            rec['rank'] = i + 1

        return recommendations[:n_recommendations]
