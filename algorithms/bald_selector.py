"""
BALD (Bayesian Active Learning by Disagreement) pair selector.

Uses PairwiseGP from BoTorch to model preferences and BALD acquisition
to select maximally informative pairs for comparison.

Aligned with art-sim-v4 simulation implementation.
"""

import numpy as np
import torch
from typing import List, Tuple, Dict, Any, Optional
from sklearn.decomposition import PCA
import concurrent.futures
from datetime import datetime

from botorch.models.pairwise_gp import PairwiseGP, PairwiseLaplaceMarginalLogLikelihood
from botorch.fit import fit_gpytorch_mll
from botorch.models.transforms.input import Normalize
from botorch.acquisition.preference import PairwiseBayesianActiveLearningByDisagreement
from botorch.optim import optimize_acqf

from .base import PairSelector

MODEL_FIT_TIMEOUT = 10  # seconds before GP fitting is considered hung


class BALDPairSelector(PairSelector):
    """
    BALD-based pair selector using Gaussian Process preference learning.

    Aligned with art-sim-v4 simulation for consistency.
    """

    def __init__(
        self,
        image_ids: List[str],
        embeddings: np.ndarray,
        pca_dimensions: int = 10,
        track_uncertainty: bool = True,
        num_restarts: int = 10,
        raw_samples: int = 256,
        n_nearest_candidates: int = 10,
        excluded_images: List[str] = None,
        burn_in_pairs: List[Tuple[str, str]] = None,
        verbose: bool = True,  # Set to False to disable detailed logging
        **kwargs
    ):
        """
        Initialize BALD pair selector.

        Args:
            image_ids: List of image identifiers
            embeddings: Original CLIP embeddings (n_images x embedding_dim)
            pca_dimensions: Number of PCA components for GP
            track_uncertainty: Whether to save uncertainty history
            num_restarts: Number of restarts for acquisition optimization
            raw_samples: Number of raw samples for acquisition optimization
            n_nearest_candidates: Number of nearest real images to consider
            excluded_images: List of image IDs to exclude (e.g., from practice trials)
            burn_in_pairs: Fixed pairs for burn-in phase (shuffled per session)
        """
        super().__init__(image_ids, excluded_images=excluded_images, **kwargs)

        # Build shuffled burn-in queue from fixed pairs (indices into image_ids)
        self._burn_in_queue: List[Tuple[int, int]] = []
        if burn_in_pairs:
            id_to_idx = {iid: i for i, iid in enumerate(image_ids)}
            self._burn_in_queue = [
                (id_to_idx[a], id_to_idx[b]) for a, b in burn_in_pairs
                if a in id_to_idx and b in id_to_idx
            ]
            np.random.shuffle(self._burn_in_queue)
        self._burn_in_index = 0

        self.pca_dimensions = pca_dimensions
        self.track_uncertainty = track_uncertainty
        self.num_restarts = num_restarts
        self.raw_samples = raw_samples
        self.n_nearest_candidates = n_nearest_candidates
        self.verbose = verbose

        # Store original embeddings
        self.original_embeddings = np.array(embeddings)

        # Apply PCA (same as simulation)
        self.pca = PCA(n_components=pca_dimensions)
        self.reduced_embeddings = self.pca.fit_transform(self.original_embeddings)
        self.train_X = torch.tensor(self.reduced_embeddings, dtype=torch.float64)

        # Compute bounds for optimization
        self.bounds = torch.stack([
            self.train_X.min(dim=0).values,
            self.train_X.max(dim=0).values
        ]).to(dtype=torch.float64)

        # Comparison history (stored as [winner_idx, loser_idx])
        self.comparisons: List[Tuple[int, int]] = []
        self.comparison_tensor: Optional[torch.Tensor] = None

        # Model state
        self.model: Optional[PairwiseGP] = None
        self.last_compared_pair: Optional[Tuple[int, int]] = None
        self.last_fitted_n_comparisons: int = 0

        # Tracking data for analysis
        self.tracking_data = {
            'pca_dimensions': pca_dimensions,
            'pca_explained_variance_ratio': self.pca.explained_variance_ratio_.tolist(),
            'n_images': len(image_ids),
            'iterations': [],
            'presented_pairs': [],
            'selected': [],
            'not_selected': [],
            'utilities_per_iteration': [],
            'uncertainties_per_iteration': [],
            'acquisition_values': [],
            'normalized_cv_per_iteration': [],
            'timestamps': [],
        }

    def _init_model(self) -> bool:
        """
        Initialize/refit the GP model with current comparisons.

        Requires at least 10 comparisons (burn-in period).
        Creates a FRESH model each refit (same as simulation).
        """
        if len(self.comparisons) < 10:
            return False

        # Only refit if new comparisons were added
        if len(self.comparisons) == self.last_fitted_n_comparisons:
            return self.model is not None

        # Start timing
        start_time = datetime.now()
        timestamp_str = start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        try:
            if self.verbose:
                print(f"\n{'='*60}")
                print(f"[{timestamp_str}] BALD Model Fitting Started")
                print(f"{'='*60}")
                print(f"  Comparisons: {len(self.comparisons)}")
                print(f"  Training data shape: {self.train_X.shape}")
                print(f"  PCA dimensions: {self.pca_dimensions}")

            self.comparison_tensor = torch.tensor(self.comparisons, dtype=torch.long)

            # Build and fit a new model in a local variable — keep the old model
            # alive until the new one is confirmed fitted, so we can fall back to it
            if self.verbose:
                print(f"  Creating PairwiseGP model...")
            new_model = PairwiseGP(
                self.train_X,
                self.comparison_tensor,
                input_transform=Normalize(d=self.train_X.shape[-1])
            )
            mll = PairwiseLaplaceMarginalLogLikelihood(new_model.likelihood, new_model)

            if self.verbose:
                print(f"  Setting model to training mode...")
            new_model.train()
            new_model.likelihood.train()

            if self.verbose:
                print(f"  Fitting GP model (timeout={MODEL_FIT_TIMEOUT}s)...")
            fit_start = datetime.now()
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = executor.submit(fit_gpytorch_mll, mll)
            try:
                future.result(timeout=MODEL_FIT_TIMEOUT)
            except concurrent.futures.TimeoutError:
                executor.shutdown(wait=False, cancel_futures=True)
                raise TimeoutError(f"GP model fitting timed out after {MODEL_FIT_TIMEOUT}s")
            executor.shutdown(wait=False)
            fit_duration = (datetime.now() - fit_start).total_seconds()

            # Fitting succeeded — swap in the new model, release the old one
            new_model.eval()
            new_model.likelihood.eval()
            del self.model
            self.model = new_model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            self.last_fitted_n_comparisons = len(self.comparisons)

            # Calculate total duration
            total_duration = (datetime.now() - start_time).total_seconds()

            if self.verbose:
                print(f"  ✓ Model fitting successful!")
                print(f"  Fitting time: {fit_duration:.3f}s")
                print(f"  Total time: {total_duration:.3f}s")
                print(f"{'='*60}\n")

            if len(self.comparisons) == 10:
                print(f"  🎯 BALD model now ACTIVE (reached 10 comparisons)")

            return True
        except Exception as e:
            # Calculate duration even on failure
            error_duration = (datetime.now() - start_time).total_seconds()
            error_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

            print(f"\n{'='*60}")
            print(f"[{error_timestamp}] ❌ BALD MODEL FITTING FAILED")
            print(f"{'='*60}")
            print(f"  Comparisons: {len(self.comparisons)}")
            print(f"  Duration: {error_duration:.3f}s")
            print(f"  Error type: {type(e).__name__}")
            print(f"  Error message: {e}")
            print(f"\n  Full traceback:")
            import traceback
            traceback.print_exc()
            print(f"{'='*60}\n")
            # Mark as attempted so we don't retry until a new comparison arrives
            self.last_fitted_n_comparisons = len(self.comparisons)
            # If a previously fitted model exists, it's still usable
            if self.model is not None:
                print(f"  ℹ Falling back to previous model")
                return True
            return False

    def _get_posterior_stats(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get utilities and uncertainties from current model."""
        if self.model is None:
            n = len(self.image_ids)
            return np.zeros(n), np.ones(n)

        with torch.no_grad():
            posterior = self.model.posterior(self.train_X)
            utilities = posterior.mean.squeeze().numpy()
            uncertainties = posterior.variance.squeeze().sqrt().numpy()

        return utilities, uncertainties

    def _find_nearest_real_images(self, suggested_X: torch.Tensor, n: int = 10) -> List[int]:
        """Find n nearest real images to suggested points (using torch.cdist like simulation)."""
        distances = torch.cdist(self.train_X, suggested_X)
        min_distances = distances.min(dim=1).values
        return torch.argsort(min_distances)[:n].tolist()

    def _select_pair_bald(self) -> Tuple[int, int, float]:
        """Use BALD acquisition to select next pair (aligned with simulation)."""
        start_time = datetime.now()
        timestamp_str = start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        if self.verbose:
            print(f"\n[{timestamp_str}] BALD pair selection started...")

        acq_function = PairwiseBayesianActiveLearningByDisagreement(pref_model=self.model)

        # Optimize acquisition function
        if self.verbose:
            print(f"  Optimizing acquisition function (restarts={self.num_restarts}, samples={self.raw_samples})...")
        acq_start = datetime.now()
        try:
            all_candidates_X, all_candidates_acq = optimize_acqf(
                acq_function=acq_function,
                bounds=self.bounds,
                q=2,
                num_restarts=self.num_restarts,
                raw_samples=self.raw_samples,
                return_best_only=False,
            )
        except Exception as e:
            print(f"  ⚠ optimize_acqf failed ({type(e).__name__}: {e}), falling back to uncertainty-based selection")
            return self._select_pair_uncertainty()
        acq_duration = (datetime.now() - acq_start).total_seconds()
        if self.verbose:
            print(f"  Acquisition optimization: {acq_duration:.3f}s")

        sorted_acq_indices = all_candidates_acq.argsort(descending=True)

        # Find valid pair (avoiding immediate repetition and excluded images)
        if self.verbose:
            print(f"  Finding valid pair from {len(sorted_acq_indices)} candidates...")
        for allow_repeat in [False, True]:
            for candidate_idx in sorted_acq_indices:
                candidate_X = all_candidates_X[candidate_idx]
                candidate_acq_val = all_candidates_acq[candidate_idx].item()

                nearest_candidates = self._find_nearest_real_images(
                    candidate_X, n=self.n_nearest_candidates
                )

                for i in range(len(nearest_candidates)):
                    for j in range(i + 1, len(nearest_candidates)):
                        candidate_a = nearest_candidates[i]
                        candidate_b = nearest_candidates[j]

                        # Skip excluded images
                        if (self.image_ids[candidate_a] in self.excluded_images or
                            self.image_ids[candidate_b] in self.excluded_images):
                            continue

                        candidate_pair = (min(candidate_a, candidate_b), max(candidate_a, candidate_b))

                        if not allow_repeat and candidate_pair == self.last_compared_pair:
                            continue

                        total_duration = (datetime.now() - start_time).total_seconds()
                        if self.verbose:
                            print(f"  ✓ Pair selected (acquisition={candidate_acq_val:.4f}, total={total_duration:.3f}s)\n")
                        return candidate_a, candidate_b, candidate_acq_val

        # No valid pair found in acquisition candidates — fall back to uncertainty-based
        if self.verbose:
            print(f"  ⚠ No valid pair in acquisition candidates, falling back to uncertainty-based selection")
        return self._select_pair_uncertainty()

    def _select_pair_burn_in(self) -> Tuple[int, int, float]:
        """Serve the next fixed burn-in pair (shuffled per session). Falls back to random if exhausted."""
        import time

        if self._burn_in_index < len(self._burn_in_queue):
            idx_a, idx_b = self._burn_in_queue[self._burn_in_index]
            self._burn_in_index += 1
        else:
            # Fallback: random pair
            available = [i for i in range(len(self.image_ids))
                         if self.image_ids[i] not in self.excluded_images]
            selected = np.random.choice(available, size=2, replace=False)
            idx_a, idx_b = int(selected[0]), int(selected[1])

        # Delay to match expected BALD latency for consistent user experience
        time.sleep(2.5)

        return idx_a, idx_b, 0.0

    def _select_pair_uncertainty(self) -> Tuple[int, int, float]:
        """Fallback pair selection using model uncertainty when optimize_acqf fails."""
        _, uncertainties = self._get_posterior_stats()

        available = [i for i in range(len(self.image_ids))
                     if self.image_ids[i] not in self.excluded_images]
        available.sort(key=lambda i: uncertainties[i], reverse=True)

        for i in range(len(available)):
            for j in range(i + 1, len(available)):
                candidate_pair = (min(available[i], available[j]), max(available[i], available[j]))
                if candidate_pair != self.last_compared_pair:
                    return available[i], available[j], 0.0

        # Fallback if last_compared_pair is the only option
        return available[0], available[1], 0.0

    def get_next_pair(self) -> Tuple[str, str]:
        """
        Get the next pair of images to compare.

        Uses random selection for burn-in (first 10), then BALD acquisition.
        """
        model_fitted = self._init_model()

        if model_fitted:
            idx_a, idx_b, acq_val = self._select_pair_bald()
        else:
            idx_a, idx_b, acq_val = self._select_pair_burn_in()

        # Store for tracking
        self.last_pair_indices = (idx_a, idx_b)
        self.last_acq_val = acq_val
        self.last_model_fitted = model_fitted
        self.last_compared_pair = (min(idx_a, idx_b), max(idx_a, idx_b))

        self.tracking_data['presented_pairs'].append([idx_a, idx_b])

        return (self.image_ids[idx_a], self.image_ids[idx_b])

    def record_comparison(self, image_1: str, image_2: str, chosen: str):
        """Record a comparison result."""
        idx_1 = self.image_ids.index(image_1)
        idx_2 = self.image_ids.index(image_2)
        chosen_idx = self.image_ids.index(chosen)

        if chosen_idx == idx_1:
            winner_idx, loser_idx = idx_1, idx_2
        else:
            winner_idx, loser_idx = idx_2, idx_1

        self.comparisons.append([winner_idx, loser_idx])

        self.tracking_data['selected'].append(winner_idx)
        self.tracking_data['not_selected'].append(loser_idx)

        # Track metrics after model is fitted
        if self.track_uncertainty and hasattr(self, 'last_model_fitted') and self.last_model_fitted:
            utilities, uncertainties = self._get_posterior_stats()

            # Normalized CV
            utility_range = utilities.max() - utilities.min()
            normalized_cv = float(uncertainties.mean() / utility_range) if utility_range > 0 else float('inf')

            self.tracking_data['iterations'].append(len(self.comparisons))
            self.tracking_data['utilities_per_iteration'].append(utilities.tolist())
            self.tracking_data['uncertainties_per_iteration'].append(uncertainties.tolist())
            self.tracking_data['acquisition_values'].append(getattr(self, 'last_acq_val', 0.0))
            self.tracking_data['normalized_cv_per_iteration'].append(normalized_cv)
            self.tracking_data['timestamps'].append(datetime.now().isoformat())

    def get_utilities(self) -> Dict[str, float]:
        """Get current utility estimates for all images."""
        utilities, _ = self._get_posterior_stats()
        return {img_id: float(utilities[i]) for i, img_id in enumerate(self.image_ids)}

    def get_uncertainties(self) -> Dict[str, float]:
        """Get current uncertainty estimates for all images."""
        _, uncertainties = self._get_posterior_stats()
        return {img_id: float(uncertainties[i]) for i, img_id in enumerate(self.image_ids)}

    def get_top_images(self, n: int = 10) -> List[Tuple[str, float, float]]:
        """Get top n images by utility."""
        utilities, uncertainties = self._get_posterior_stats()
        sorted_indices = np.argsort(utilities)[::-1][:n]

        return [
            (self.image_ids[idx], float(utilities[idx]), float(uncertainties[idx]))
            for idx in sorted_indices
        ]

    def get_tracking_data(self) -> Dict[str, Any]:
        """Get all tracking data for visualization/export."""
        data = self.tracking_data.copy()

        if len(self.comparisons) > 0:
            utilities, uncertainties = self._get_posterior_stats()
            data['final_utilities'] = utilities.tolist()
            data['final_uncertainties'] = uncertainties.tolist()
            data['total_comparisons'] = len(self.comparisons)
            data['image_ids'] = self.image_ids

        return data

    def get_consistency_metrics(self) -> Dict[str, float]:
        """Compute metrics about model convergence."""
        metrics = {}

        if len(self.tracking_data['normalized_cv_per_iteration']) > 1:
            cvs = self.tracking_data['normalized_cv_per_iteration']
            metrics['final_normalized_cv'] = cvs[-1]
            if len(cvs) > 2:
                trend = np.polyfit(range(len(cvs)), cvs, 1)[0]
                metrics['uncertainty_trend'] = float(trend)

        if len(self.tracking_data['selected']) > 0:
            unique_selected = len(set(self.tracking_data['selected']))
            total_selections = len(self.tracking_data['selected'])
            metrics['selection_diversity'] = unique_selected / total_selections

        return metrics
