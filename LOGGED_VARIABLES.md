# Logged Variables — Experiment Platform

All per-session exports land in `data_exports/{participant_id}_{timestamp}/`.

---

## `comparisons.csv` — one row per pairwise comparison

| Field | Type | Description |
|---|---|---|
| `phase` | string | `practice` or `main` |
| `trial_number` | int | 0-indexed counter, resets per phase |
| `image_1` | string | First image ID (server order, pre-randomisation). `practice_a` / `practice_b` during practice. |
| `image_2` | string | Second image ID (server order, pre-randomisation). |
| `chosen` | string | ID of the image the participant selected |
| `chosen_side` | string | `left` or `right` — which screen position was clicked. Only way to recover display layout. |
| `onset_timestamp` | ISO 8601 | When the pair was rendered on screen (client-side) |
| `decision_timestamp` | ISO 8601 | When the participant clicked (client-side) |
| `response_time_ms` | int | `decision_timestamp − onset_timestamp` in ms (client-side) |

**Notes:**
- Practice trials use placeholder IDs (`practice_a`/`practice_b`) and are not fed into the model.
- `image_1`/`image_2` are always in the order the server returned them. Left/right display is randomised independently each trial — use `chosen_side` to recover it.

---

## `surveys.csv` — mid-study check-ins

Shown every `survey_interval` main trials (configurable; default 10).

| Field | Type | Description |
|---|---|---|
| `comparison_number` | int | `mainCount` at the time the survey was shown |
| `certainty` | int | Likert rating: how certain the participant feels about their choices |
| `know_prefs` | int | Likert rating: how well they feel they know their own preferences |
| `strategy` | string | Free-text description of their comparison strategy |
| `timestamp` | ISO 8601 | Server-side timestamp when the response was saved |

---

## `study_surveys.json` — demographics + post-study scales

```json
{
  "demographics": { "age_range", "gender", "education" },
  "trust":        { "trust1"–"trust6" },          // 1–5 Likert
  "ati":          { "ati1"–"ati9" },              // 1–6 Likert
  "timestamps":   { "demographics_collected", "trust_collected", "ati_collected" }
}
```

| Section | Items | Scale | Notes |
|---|---|---|---|
| `demographics` | age_range, gender, education | categorical | Collected at session start |
| `trust` | trust1–trust6 | 1–5 | Propensity-to-trust scale; items presented in shuffled order |
| `ati` | ati1–ati9 | 1–6 | Affinity for Technology Interaction; items presented in shuffled order |

**Reverse-scored items** (noted in client code, not pre-reversed in the export):
- Trust: `trust2`
- ATI: `ati3`, `ati6`, `ati8`

---

## `bald_tracking.json` — BALD algorithm internals (BALD sessions only)

Top-level config:

| Field | Description |
|---|---|
| `pca_dimensions` | Number of PCA components used for the GP |
| `pca_explained_variance_ratio` | Per-component explained variance (length = pca_dimensions) |
| `n_images` | Total image pool size |

Per-iteration arrays (all length = number of comparisons after burn-in):

| Field | Description |
|---|---|
| `iterations[]` | Comparison count at each logged step (starts at 11 — first 10 are burn-in) |
| `presented_pairs[]` | `[idx_a, idx_b]` indices into the image pool |
| `selected[]` | Winner index |
| `not_selected[]` | Loser index |
| `utilities_per_iteration[]` | Full posterior-mean vector (length 400) at that step |
| `uncertainties_per_iteration[]` | Full posterior-std vector (length 400) at that step |
| `acquisition_values[]` | BALD acquisition value for the presented pair (0.0 during burn-in) |
| `normalized_cv_per_iteration[]` | `mean(uncertainty) / range(utility)` — convergence proxy |
| `timestamps[]` | Server-side ISO 8601 per iteration |

Final snapshot:

| Field | Description |
|---|---|
| `final_utilities[]` | Posterior mean at session end |
| `final_uncertainties[]` | Posterior std at session end |
| `total_comparisons` | Total main-phase comparisons |
| `image_ids[]` | Ordered image ID list (index key for all per-image vectors) |

---

## `consistency_metrics.json` — convergence summary (BALD sessions only)

| Field | Description |
|---|---|
| `final_normalized_cv` | Last value of `mean(uncertainty) / range(utility)` |
| `uncertainty_trend` | Slope of a linear fit over the normalized-CV series (negative = converging) |
| `selection_diversity` | `unique_winners / total_selections` — 1.0 = all different images chosen |

---

## `recommendations.json` — recommendation output

| Field | Description |
|---|---|
| `chosen_images[]` | All winner IDs from main phase (input to the recommender) |
| `recommendations[]` | Ranked list of recommended images (see below) |
| `recommendation_type` | Always `"manual"` currently |
| `recommender_used` | `"utility"` (BALD-learned) or `"embedding"` (CLIP similarity) |
| `timestamp` | Server-side ISO 8601 |

Each item in `recommendations[]`:

| Field | Description |
|---|---|
| `image_id` | Image identifier |
| `score` | Utility score from the model |
| `uncertainty` | Posterior std for this image |
| `rank` | 1-based rank by score |
| `metadata` | `{style, artist, title, year, filename, relative_path}` |
| `path` | URL path to serve the image |

---

## `final_ratings.json` — participant's rating of their recommendation

| Field | Description |
|---|---|
| `rating` | 1–5 star rating of how good the recommendation felt |
| `recommendation_type` | `"manual"` |
| `selected_artwork` | The recommendation object(s) the participant chose (single object or array) |
| `timestamp` | Server-side ISO 8601 |

---

## `pair_loading_times.json` — client-side performance telemetry

| Field | Description |
|---|---|
| `loading_times[]` | Per-trial ms from participant's click on the previous pair to the next pair appearing. First main trial is excluded (no preceding click). |
| `mean` / `std` / `min` / `max` | Summary stats (rounded to integer ms) |
| `count` | Number of recorded loading times (`n_main − 1`) |

---

## `session_metadata.json` — session-level config snapshot

| Field | Description |
|---|---|
| `session_id` | `{participant_id}_{YYYYMMDD_HHMMSS}` |
| `participant_id` | Auto-generated `P_xxxx` |
| `start_time` / `end_time` | Server-side ISO 8601 |
| `config.n_practice` | Number of practice trials |
| `config.n_main` | Number of main trials |
| `config.algorithm` | `"bald"` or `"random"` |
| `config.recommender` | `"utility"` or `"embedding"` |
| `config.survey_interval` | Mid-study survey frequency (every N main trials) |
| `config.recommendations.manual_show_n` | How many recommendations were shown |
| `config.recommendations.manual_select_n` | How many the participant could pick |
| `algorithm_used` | Actual algorithm (may differ from config if BALD unavailable) |
| `total_comparisons` | Practice + main combined |
