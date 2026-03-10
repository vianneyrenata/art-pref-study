# WikiArt Preference Study - Experiment Platform

A web-based experiment platform for studying art preferences through pairwise comparisons, with personalized recommendations based on CLIP embeddings and optional BALD (Bayesian Active Learning by Disagreement) pair selection.

## Quick Start

```bash
# 1. Install dependencies
pip install flask chromadb open-clip-torch pillow numpy

# For BALD algorithm (optional):
pip install botorch scikit-learn

# 2. Run the server
cd experiments/experiment-platform
python3 app.py

# 3. Open in browser
# http://localhost:5001
```

## Configuration

All settings are in **`config.json`** - edit with any text editor:

```json
{
  "experiment": {
    "n_practice_trials": 3,
    "n_main_trials": 10,
    "survey_interval": 5
  },

  "algorithms": {
    "pair_selector": "random",
    "recommender": "embedding",
    "bald": {
      "pca_dimensions": 10,
      "track_uncertainty": true
    }
  },

  "recommendations": {
    "manual_show_n": 3,
    "manual_select_n": 1
  },

  "paths": {
    "db_path": "../sample-mini-db",
    "collection_name": "sample-mini",
    "images_base_path": "../wikiart-sample-mini",
    "data_exports_path": "./data_exports"
  }
}
```

### Config Options

#### Experiment Settings

| Setting | Description | Options |
|---------|-------------|---------|
| `n_practice_trials` | Number of warm-up comparisons | Any integer (default: 3) |
| `n_main_trials` | Number of main comparisons | Any integer (default: 10) |
| `survey_interval` | Survey frequency during main trials | 0 = off, or any integer |

#### Algorithm Settings

| Setting | Description | Options |
|---------|-------------|---------|
| `pair_selector` | Algorithm for selecting image pairs | `"random"`, `"bald"` |
| `recommender` | Algorithm for final recommendations | `"embedding"`, `"utility"` |

#### BALD Settings (when `pair_selector: "bald"`)

| Setting | Description | Default |
|---------|-------------|---------|
| `pca_dimensions` | PCA dimensions for GP embeddings | 10 |
| `track_uncertainty` | Save per-item uncertainty history | true |

#### Recommendation Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `manual_show_n` | Number of options shown for manual selection | 3 |
| `manual_select_n` | Number user can select (supports multi-select) | 1 |

### Algorithm Details

**Pair Selectors:**
- `random`: Randomly selects pairs for comparison
- `bald`: Uses BoTorch's PairwiseGP with BALD acquisition to select maximally informative pairs (requires `pip install botorch`)

**Recommenders:**
- `embedding`: Uses CLIP embedding similarity to recommend images similar to user's choices
- `utility`: Uses learned utility scores from BALD model (only works with `pair_selector: "bald"`)

## Experiment Flow

1. **Welcome/Consent** - Study information and consent
2. **Demographics** - Optional participant ID and age range
3. **Practice Trials** - Warm-up comparisons (not recorded for recommendations)
4. **Main Trials** - Pairwise comparisons with periodic surveys
5. **Recommendation Choice** - Auto (1 pick) or Manual (choose from 3)
6. **Final Rating** - Rate the recommendation (1-5)
7. **Debrief** - Study complete

## Data Output

Each session creates a folder in `data_exports/` with:

```
data_exports/
  {participant_id}_{timestamp}/
    session_metadata.json    # Session info, config, demographics
    comparisons.csv          # All pairwise comparison data
    surveys.csv              # Survey responses
    recommendations.json     # Generated recommendations
    final_ratings.json       # Final rating and selected artwork

    # BALD-only files (when pair_selector: "bald"):
    bald_tracking.json       # Per-iteration utilities, uncertainties, acquisition values
    consistency_metrics.json # User consistency/noise metrics
```

### comparisons.csv columns

| Column | Description |
|--------|-------------|
| `phase` | "practice" or "main" |
| `trial_number` | Trial index within phase |
| `image_1`, `image_2` | Image IDs shown |
| `chosen` | ID of selected image |
| `chosen_side` | "left" or "right" |
| `response_time_ms` | Time to respond |
| `timestamp` | ISO timestamp |

### BALD Tracking Data (bald_tracking.json)

When using the BALD algorithm, additional tracking data is saved:

| Field | Description |
|-------|-------------|
| `utilities_per_iteration` | Utility estimates for all images after each comparison |
| `uncertainties_per_iteration` | Uncertainty (std) for all images after each comparison |
| `normalized_cv_per_iteration` | Coefficient of variation (uncertainty/utility range) over time |
| `top20_rank_consistency` | Jaccard similarity of top-20 rankings across iterations |
| `acquisition_values` | BALD acquisition values for selected pairs |
| `embedding_distances` | Euclidean distance between presented pairs (in CLIP space) |
| `presented_pairs` | [idx_a, idx_b] indices of pairs shown |
| `selected` / `not_selected` | Indices of chosen and not-chosen images |

### Consistency Metrics (consistency_metrics.json)

Metrics for analyzing user behavior:

| Metric | Description |
|--------|-------------|
| `avg_pair_distance` | Average embedding distance of compared pairs |
| `uncertainty_trend` | Slope of uncertainty over time (negative = learning) |
| `final_rank_consistency` | Final top-20 ranking stability |
| `selection_diversity` | Ratio of unique images selected to total selections |

## Directory Structure

```
experiment-platform/
  app.py              # Flask backend
  config.json         # Configuration (edit this!)
  algorithms/         # Pair selection & recommendation algorithms
    base.py           # Abstract base classes
    random_pairs.py   # Random pair selector
    bald_selector.py  # BALD pair selector (BoTorch)
    recommender.py    # Embedding-based recommender
    utility_recommender.py  # Utility-based recommender (for BALD)
  static/
    app.js            # Frontend logic
    style.css         # Styling
  templates/
    index.html        # Main page
  data_exports/       # Output data (created automatically)

../sample-mini-db/    # ChromaDB with CLIP embeddings
../wikiart-sample-mini/  # Source images
```

## Recreating the Database

If you need to rebuild the ChromaDB collection with new images:

```bash
cd /path/to/llm-wikiart
python3 create_sample_mini_db.py
```

Images should be organized as:
```
wikiart-sample-mini/
  StyleName/
    artist-name_title-of-artwork-year.jpg
```

Metadata (artist, title, year) is automatically parsed from filenames.

## Troubleshooting

**Port already in use:**
```bash
# Kill existing process
pkill -f "python3 app.py"
# Or use a different port
python3 app.py  # Edit app.py to change port
```

**Missing dependencies:**
```bash
pip install flask chromadb open-clip-torch pillow numpy
```

**Database errors:**
- Ensure `../sample-mini-db` exists and contains the ChromaDB collection
- Run `create_sample_mini_db.py` to recreate if needed
