"""
WikiArt Preference Study - Experiment Platform

A modular experiment platform for studying art preferences through
pairwise comparisons with pluggable algorithms.
"""

import os
import json
import csv
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_from_directory
import chromadb
import numpy as np
import boto3
from botocore.exceptions import ClientError

from algorithms import RandomPairSelector, EmbeddingRecommender, BALD_AVAILABLE
if BALD_AVAILABLE:
    from algorithms import BALDPairSelector, UtilityRecommender

app = Flask(__name__)

# === CONFIGURATION ===
def load_config():
    """Load configuration from config.json"""
    config_path = Path(__file__).parent / 'config.json'
    with open(config_path, 'r') as f:
        cfg = json.load(f)

    return {
        'N_PRACTICE_TRIALS': cfg['experiment']['n_practice_trials'],
        'N_MAIN_TRIALS': cfg['experiment']['n_main_trials'],
        'SURVEY_INTERVAL': cfg['experiment']['survey_interval'],
        'DB_PATH': cfg['paths']['db_path'],
        'COLLECTION_NAME': cfg['paths']['collection_name'],
        'IMAGES_BASE_PATH': cfg['paths']['images_base_path'],
        'DATA_EXPORTS_PATH': cfg['paths']['data_exports_path'],
        'ALGORITHM': cfg['algorithms']['pair_selector'],
        'RECOMMENDER': cfg['algorithms']['recommender'],
        # BALD settings
        'PCA_DIMENSIONS': cfg['algorithms'].get('bald', {}).get('pca_dimensions', 10),
        'TRACK_UNCERTAINTY': cfg['algorithms'].get('bald', {}).get('track_uncertainty', True),
        # Recommendation settings
        'MANUAL_SHOW_N': cfg.get('recommendations', {}).get('manual_show_n', 3),
        'MANUAL_SELECT_N': cfg.get('recommendations', {}).get('manual_select_n', 1),
        # S3 backup settings
        'S3_ENABLED': cfg.get('s3', {}).get('enabled', False),
        'S3_BUCKET': cfg.get('s3', {}).get('bucket_name', ''),
        'S3_PARTICIPANT_PREFIX': cfg.get('s3', {}).get('participant_prefix', 'participant'),
        'S3_RESEARCHER_PREFIX': cfg.get('s3', {}).get('researcher_prefix', 'researcher'),
    }

CONFIG = load_config()

# === GLOBAL STATE ===
# In production, use proper session management (Redis, database, etc.)
sessions = {}

# === S3 BACKUP ===
def backup_session_to_s3(session_id, study_code=None):
    """Backup session data to S3 after completion.

    Args:
        session_id: Session ID to backup
        study_code: Optional study code (one, two, three) to determine backup path
    """
    if not CONFIG['S3_ENABLED'] or not CONFIG['S3_BUCKET']:
        return  # S3 backup disabled

    if session_id not in sessions:
        print(f"Cannot backup session {session_id}: not found")
        return

    session = sessions[session_id]
    export_path = Path(session['export_path'])

    if not export_path.exists():
        print(f"Cannot backup session {session_id}: export path does not exist")
        return

    try:
        s3_client = boto3.client('s3')
        bucket = CONFIG['S3_BUCKET']

        # Determine S3 prefix based on study code
        # study=three goes to researcher/, others go to participant/
        if study_code == 'three':
            prefix = CONFIG['S3_RESEARCHER_PREFIX']
        else:
            prefix = CONFIG['S3_PARTICIPANT_PREFIX']

        # Upload all files in the session export directory
        for file_path in export_path.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(export_path.parent)
                s3_key = f"{prefix}/{relative_path}"

                with open(file_path, 'rb') as f:
                    s3_client.upload_fileobj(f, bucket, s3_key)

                print(f"Uploaded {file_path.name} to s3://{bucket}/{s3_key}")

        print(f"Session {session_id} backed up to S3: {prefix}/")

    except ClientError as e:
        print(f"Error backing up session {session_id} to S3: {e}")
    except Exception as e:
        print(f"Unexpected error backing up session {session_id} to S3: {e}")

# Cache for style folder names (computed once at startup for fast image serving)
_style_folders_cache = None

def get_style_folders():
    """Get cached list of style folder names, sorted by length (longest first)."""
    global _style_folders_cache
    if _style_folders_cache is None:
        images_path = Path(__file__).parent / CONFIG['IMAGES_BASE_PATH']
        _style_folders_cache = sorted(
            [d.name for d in images_path.iterdir() if d.is_dir()],
            key=len,
            reverse=True
        )
    return _style_folders_cache


def get_image_ids_from_db(include_embeddings=False):
    """Load all image IDs from ChromaDB, optionally with embeddings."""
    db_path = Path(__file__).parent / CONFIG['DB_PATH']
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection(name=CONFIG['COLLECTION_NAME'])

    includes = ['metadatas']
    if include_embeddings:
        includes.append('embeddings')

    results = collection.get(include=includes)

    if include_embeddings:
        return results['ids'], results['metadatas'], np.array(results['embeddings'])
    return results['ids'], results['metadatas'], None


def create_session(participant_id: str, demographics: dict = None, algorithm: str = None) -> dict:
    """Create a new experiment session.

    Args:
        participant_id: Unique participant identifier
        demographics: Demographic information
        algorithm: Override algorithm ('bald' or 'random'). If None, uses CONFIG setting.
    """
    session_id = f"{participant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Determine if we need embeddings (for BALD algorithm)
    # Use provided algorithm parameter, otherwise fall back to CONFIG
    selected_algorithm = algorithm if algorithm else CONFIG['ALGORITHM']
    use_bald = selected_algorithm == 'bald' and BALD_AVAILABLE
    need_embeddings = use_bald

    # Get available images (and embeddings if needed)
    image_ids, metadatas, embeddings = get_image_ids_from_db(include_embeddings=need_embeddings)

    # Create metadata lookup
    metadata_lookup = {id_: meta for id_, meta in zip(image_ids, metadatas)}

    # Load fixed burn-in pairs
    burn_in_pairs_path = Path(__file__).parent / 'data' / 'burn_in_pairs.json'
    burn_in_pairs = None
    if burn_in_pairs_path.exists():
        with open(burn_in_pairs_path) as f:
            burn_in_pairs = [(p['image_1'], p['image_2']) for p in json.load(f)['pairs']]

    # Initialize pair selector based on config
    if use_bald:
        selector = BALDPairSelector(
            image_ids=image_ids,
            embeddings=embeddings,
            pca_dimensions=CONFIG['PCA_DIMENSIONS'],
            track_uncertainty=CONFIG['TRACK_UNCERTAINTY'],
            burn_in_pairs=burn_in_pairs,
        )
        print(f"  Using BALD selector with {CONFIG['PCA_DIMENSIONS']} PCA dimensions")
    else:
        selector = RandomPairSelector(image_ids, burn_in_pairs=burn_in_pairs)
        if CONFIG['ALGORITHM'] == 'bald' and not BALD_AVAILABLE:
            print("  Warning: BALD requested but BoTorch not available, using random")

    # Create data export folder
    export_path = Path(CONFIG['DATA_EXPORTS_PATH']) / session_id
    export_path.mkdir(parents=True, exist_ok=True)

    session = {
        'session_id': session_id,
        'participant_id': participant_id,
        'selector': selector,
        'metadata_lookup': metadata_lookup,
        'image_ids': image_ids,
        'embeddings': embeddings,  # Store for utility recommender
        'export_path': str(export_path),
        'phase': 'practice',  # 'practice', 'main', 'recommendations', 'complete'
        'practice_count': 0,
        'main_count': 0,
        'comparisons': [],
        'surveys': [],
        'start_time': datetime.now().isoformat(),
        'demographics': demographics or {},
        'use_bald': use_bald,
        'algorithm': selected_algorithm,  # Track which algorithm was assigned
    }

    sessions[session_id] = session
    return session


def get_participant_folder(session_id: str) -> Path:
    """Get the data export folder for a session."""
    if session_id in sessions:
        return Path(sessions[session_id]['export_path'])
    return Path(CONFIG['DATA_EXPORTS_PATH']) / session_id


# === ROUTES ===

@app.route('/')
def index():
    """Serve the main experiment page."""
    return render_template('index.html', config={
        'n_practice': CONFIG['N_PRACTICE_TRIALS'],
        'n_main': CONFIG['N_MAIN_TRIALS'],
    })


@app.route('/api/get_config', methods=['GET'])
def get_config():
    """Get experiment configuration for display."""
    return jsonify({
        'success': True,
        'n_practice': CONFIG['N_PRACTICE_TRIALS'],
        'n_main': CONFIG['N_MAIN_TRIALS'],
    })


@app.route('/images/<path:filepath>')
def serve_image(filepath):
    """Serve images from the wikiart directory.

    Converts database ID format (Style_filename) to file path (Style/filename.jpg)
    Handles style names with underscores like Post_Impressionism.
    Uses cached style folder list for fast lookups.
    """
    images_path = Path(__file__).parent / CONFIG['IMAGES_BASE_PATH']

    # Convert Style_filename to Style/filename.jpg
    if '_' in filepath and '/' not in filepath:
        # Use cached style folders (already sorted by length)
        for style in get_style_folders():
            if filepath.startswith(style + '_'):
                filename = filepath[len(style) + 1:]
                filepath = f"{style}/{filename}.jpg"
                break

    return send_from_directory(str(images_path), filepath)


@app.route('/api/start_session', methods=['POST'])
def start_session():
    """Start a new experiment session."""
    data = request.json
    participant_id = data.get('participant_id', 'anonymous')
    demographics = data.get('demographics', {})

    # Read algorithm from request body (set by frontend from URL parameter)
    study_code = data.get('study')

    # Map study codes to algorithms (discreet naming)
    algorithm = None
    if study_code == 'one':
        algorithm = 'bald'
    elif study_code == 'two':
        algorithm = 'random'
    # If no study code provided, will use default from CONFIG

    session = create_session(participant_id, demographics, algorithm=algorithm)

    # Save session metadata (config and tracking info only)
    metadata = {
        'session_id': session['session_id'],
        'participant_id': participant_id,
        'start_time': session['start_time'],
        'assigned_algorithm': session['algorithm'],  # Record which algorithm was assigned
        'study_code': study_code,  # Record the study URL parameter for reference
        'config': {
            'n_practice': CONFIG['N_PRACTICE_TRIALS'],
            'n_main': CONFIG['N_MAIN_TRIALS'],
            'algorithm': session['algorithm'],  # Use actual assigned algorithm, not CONFIG
            'recommender': CONFIG['RECOMMENDER'],
            'survey_interval': CONFIG['SURVEY_INTERVAL'],
            'recommendations': {
                'manual_show_n': CONFIG['MANUAL_SHOW_N'],
                'manual_select_n': CONFIG['MANUAL_SELECT_N'],
            },
        },
    }

    export_path = Path(session['export_path'])
    with open(export_path / 'session_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)

    # Initialize study_surveys.json with demographics
    study_surveys = {
        'demographics': demographics,
        'trust': None,  # Will be filled later
        'ati': None,    # Will be filled later
        'timestamps': {
            'demographics_collected': datetime.now().isoformat()
        }
    }

    with open(export_path / 'study_surveys.json', 'w') as f:
        json.dump(study_surveys, f, indent=2)

    return jsonify({
        'success': True,
        'session_id': session['session_id'],
        'n_practice': CONFIG['N_PRACTICE_TRIALS'],
        'n_main': CONFIG['N_MAIN_TRIALS'],
        'survey_interval': CONFIG['SURVEY_INTERVAL'],
        'recommendations': {
            'manual_show_n': CONFIG['MANUAL_SHOW_N'],
            'manual_select_n': CONFIG['MANUAL_SELECT_N'],
        },
        'algorithm': session['algorithm'],  # Return actual assigned algorithm
    })


@app.route('/api/get_next_pair', methods=['POST'])
def get_next_pair():
    """Get the next pair of images to compare (main phase only - practice uses client-side placeholders)."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]
    selector = session['selector']

    try:
        img1, img2 = selector.get_next_pair()
    except Exception as e:
        print(f"  ⚠ Pair selection failed ({type(e).__name__}: {e}), falling back to random pair")
        indices = np.random.choice(len(session['image_ids']), size=2, replace=False)
        img1, img2 = session['image_ids'][indices[0]], session['image_ids'][indices[1]]

    # Get metadata for both images
    meta1 = session['metadata_lookup'].get(img1, {})
    meta2 = session['metadata_lookup'].get(img2, {})

    return jsonify({
        'success': True,
        'pair': {
            'image_1': {
                'id': img1,
                'path': f'/images/{img1}',
                'metadata': meta1,
            },
            'image_2': {
                'id': img2,
                'path': f'/images/{img2}',
                'metadata': meta2,
            },
        },
        'phase': session['phase'],
        'trial_number': session['main_count'],
    })


@app.route('/api/submit_comparison', methods=['POST'])
def submit_comparison():
    """Submit a comparison result."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]
    selector = session['selector']

    # Record the comparison
    comparison = {
        'phase': session['phase'],
        'trial_number': session['practice_count'] if session['phase'] == 'practice' else session['main_count'],
        'image_1': data['image_1'],
        'image_2': data['image_2'],
        'chosen': data['chosen'],
        'chosen_side': data.get('chosen_side'),
        'onset_timestamp': data.get('onset_timestamp'),
        'decision_timestamp': data.get('decision_timestamp'),
        'response_time_ms': data.get('response_time_ms'),
    }

    session['comparisons'].append(comparison)

    # Only record in selector if it's a main trial (not practice)
    # Practice trials use separate images and are just for UI familiarization
    if session['phase'] != 'practice':
        selector.record_comparison(data['image_1'], data['image_2'], data['chosen'])

    # Update counters
    if session['phase'] == 'practice':
        session['practice_count'] += 1
        if session['practice_count'] >= CONFIG['N_PRACTICE_TRIALS']:
            session['phase'] = 'main'
    else:
        session['main_count'] += 1
        if session['main_count'] >= CONFIG['N_MAIN_TRIALS']:
            session['phase'] = 'recommendations'

    # Save comparison to CSV
    save_comparison_to_csv(session, comparison)

    return jsonify({
        'success': True,
        'phase': session['phase'],
        'practice_complete': session['practice_count'] >= CONFIG['N_PRACTICE_TRIALS'],
        'main_complete': session['main_count'] >= CONFIG['N_MAIN_TRIALS'],
        'practice_count': session['practice_count'],
        'main_count': session['main_count'],
    })


def save_comparison_to_csv(session: dict, comparison: dict):
    """Save a comparison to the CSV file."""
    export_path = Path(session['export_path'])
    csv_path = export_path / 'comparisons.csv'

    file_exists = csv_path.exists()

    with open(csv_path, 'a', newline='') as f:
        fieldnames = ['phase', 'trial_number', 'image_1', 'image_2', 'chosen',
                      'chosen_side', 'onset_timestamp', 'decision_timestamp', 'response_time_ms']
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(comparison)


@app.route('/api/save_survey', methods=['POST'])
def save_survey():
    """Save a mid-study survey response."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]

    survey_response = {
        'comparison_number': data.get('comparison_number'),
        'survey_data': data.get('survey_data', {}),
        'timestamp': datetime.now().isoformat(),
    }

    session['surveys'].append(survey_response)

    # Save to CSV
    export_path = Path(session['export_path'])
    csv_path = export_path / 'surveys.csv'

    file_exists = csv_path.exists()

    with open(csv_path, 'a', newline='') as f:
        fieldnames = ['comparison_number', 'certainty', 'know_prefs', 'features_like', 'features_dislike', 'timestamp']
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        survey_data = data.get('survey_data', {})
        writer.writerow({
            'comparison_number': data.get('comparison_number'),
            'certainty': survey_data.get('certainty'),
            'know_prefs': survey_data.get('know_prefs'),
            'features_like': survey_data.get('features_like', ''),
            'features_dislike': survey_data.get('features_dislike', ''),
            'timestamp': datetime.now().isoformat(),
        })

    return jsonify({'success': True})


@app.route('/api/get_recommendations', methods=['POST'])
def get_recommendations():
    """Get recommendations based on user preferences."""
    data = request.json
    session_id = data.get('session_id')
    n_recommendations = data.get('n_recommendations', 10)
    recommendation_type = 'manual'  # Always manual now

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]

    # Get chosen images from main trials only
    chosen_images = [
        c['chosen'] for c in session['comparisons']
        if c['phase'] == 'main'
    ]

    if not chosen_images:
        return jsonify({
            'success': False,
            'error': 'No choices recorded',
            'recommendations': []
        })

    # Choose recommender based on config and session state
    use_utility = (
        CONFIG['RECOMMENDER'] == 'utility' and
        session.get('use_bald', False) and
        BALD_AVAILABLE
    )

    if use_utility:
        # Use utility-based recommender with learned preferences
        recommender = UtilityRecommender(bald_selector=session['selector'])
        recommendations = recommender.generate_recommendations(
            n_recommendations=n_recommendations,
            exclude_chosen=True
        )
        recommender_used = 'utility'
    else:
        # Use embedding-based recommender
        db_path = Path(__file__).parent / CONFIG['DB_PATH']
        recommender = EmbeddingRecommender(
            db_path=str(db_path),
            collection_name=CONFIG['COLLECTION_NAME']
        )
        recommendations = recommender.generate_recommendations(
            chosen_images=chosen_images,
            n_recommendations=n_recommendations,
            exclude_chosen=True
        )
        recommender_used = 'embedding'

    # Add image paths and metadata
    for rec in recommendations:
        rec['path'] = f"/images/{rec['image_id']}"
        if 'metadata' not in rec or not rec['metadata']:
            rec['metadata'] = session['metadata_lookup'].get(rec['image_id'], {})

    # Save recommendations
    export_path = Path(session['export_path'])
    with open(export_path / 'recommendations.json', 'w') as f:
        json.dump({
            'chosen_images': chosen_images,
            'recommendations': recommendations,
            'recommendation_type': recommendation_type,
            'recommender_used': recommender_used,
            'timestamp': datetime.now().isoformat(),
        }, f, indent=2)

    return jsonify({
        'success': True,
        'recommendations': recommendations,
        'based_on': len(chosen_images),
        'recommender': recommender_used,
        'type': recommendation_type,
    })


@app.route('/api/submit_rating', methods=['POST'])
def submit_rating():
    """Submit final ratings for recommendations."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]
    session['phase'] = 'complete'
    session['end_time'] = datetime.now().isoformat()

    export_path = Path(session['export_path'])

    # Save ratings
    with open(export_path / 'final_ratings.json', 'w') as f:
        json.dump({
            'rating': data.get('rating'),
            'recommendation_type': data.get('recommendation_type'),
            'selected_artwork': data.get('selected_artwork'),
            'timestamp': datetime.now().isoformat(),
        }, f, indent=2)

    # Save BALD tracking data if using BALD selector
    if session.get('use_bald', False) and hasattr(session['selector'], 'get_tracking_data'):
        tracking_data = session['selector'].get_tracking_data()
        with open(export_path / 'bald_tracking.json', 'w') as f:
            json.dump(tracking_data, f, indent=2)

        # Also save consistency metrics
        if hasattr(session['selector'], 'get_consistency_metrics'):
            consistency_metrics = session['selector'].get_consistency_metrics()
            with open(export_path / 'consistency_metrics.json', 'w') as f:
                json.dump(consistency_metrics, f, indent=2)

    # Update session metadata with end time
    metadata_path = export_path / 'session_metadata.json'
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        metadata['end_time'] = session['end_time']
        metadata['algorithm_used'] = 'bald' if session.get('use_bald') else 'random'
        metadata['total_comparisons'] = len(session['comparisons'])
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

    return jsonify({
        'success': True,
        'message': 'Study complete! Thank you for participating.',
    })


@app.route('/api/session_stats', methods=['POST'])
def session_stats():
    """Get current session statistics."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]

    stats = {
        'session_id': session_id,
        'phase': session['phase'],
        'practice_count': session['practice_count'],
        'main_count': session['main_count'],
        'total_comparisons': len(session['comparisons']),
        'algorithm': 'bald' if session.get('use_bald') else 'random',
    }

    # Add BALD-specific stats if available
    if session.get('use_bald') and hasattr(session['selector'], 'get_consistency_metrics'):
        stats['bald_metrics'] = session['selector'].get_consistency_metrics()

    return jsonify(stats)


@app.route('/api/bald_stats', methods=['POST'])
def bald_stats():
    """Get BALD algorithm statistics for debugging/monitoring."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]

    if not session.get('use_bald'):
        return jsonify({
            'error': 'Session not using BALD algorithm',
            'algorithm': 'random'
        }), 400

    selector = session['selector']

    # Get current utilities and uncertainties
    utilities = selector.get_utilities()
    uncertainties = selector.get_uncertainties()

    # Get top images
    top_images = selector.get_top_images(n=10)

    # Get consistency metrics
    consistency = selector.get_consistency_metrics()

    return jsonify({
        'success': True,
        'n_comparisons': len(selector.comparisons),
        'top_10_images': [
            {'image_id': img_id, 'utility': util, 'uncertainty': unc}
            for img_id, util, unc in top_images
        ],
        'consistency_metrics': consistency,
        'pca_explained_variance': selector.tracking_data['pca_explained_variance_ratio'],
    })


@app.route('/api/save_trust_survey', methods=['POST'])
def save_trust_survey():
    """Save propensity to trust survey responses."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]
    export_path = Path(session['export_path'])

    # Update study_surveys.json with trust data
    surveys_path = export_path / 'study_surveys.json'
    with open(surveys_path, 'r') as f:
        study_surveys = json.load(f)

    study_surveys['trust'] = data.get('trust_data', {})
    study_surveys['timestamps']['trust_collected'] = datetime.now().isoformat()

    with open(surveys_path, 'w') as f:
        json.dump(study_surveys, f, indent=2)

    return jsonify({'success': True})


@app.route('/api/save_ati_survey', methods=['POST'])
def save_ati_survey():
    """Save ATI (Affinity for Technology Interaction) survey responses."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]
    export_path = Path(session['export_path'])

    # Update study_surveys.json with ATI data
    surveys_path = export_path / 'study_surveys.json'
    with open(surveys_path, 'r') as f:
        study_surveys = json.load(f)

    study_surveys['ati'] = data.get('ati_data', {})
    study_surveys['timestamps']['ati_collected'] = datetime.now().isoformat()

    with open(surveys_path, 'w') as f:
        json.dump(study_surveys, f, indent=2)

    return jsonify({'success': True})


@app.route('/api/submit_ranking', methods=['POST'])
def submit_ranking():
    """Save ranking data from drag-and-drop ranking interface."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]
    export_path = Path(session['export_path'])

    # Add timestamp to ranking data
    ranking_data = data.get('ranking_data', {})
    ranking_data['timestamp'] = datetime.now().isoformat()

    # Save to ranking_data.json
    with open(export_path / 'ranking_data.json', 'w') as f:
        json.dump(ranking_data, f, indent=2)

    return jsonify({'success': True})


@app.route('/api/submit_ranking_unselected', methods=['POST'])
def submit_ranking_unselected():
    """Save ranking data for unselected images from second ranking interface."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]
    export_path = Path(session['export_path'])

    # Add timestamp to ranking data
    ranking_data = data.get('ranking_data', {})
    ranking_data['timestamp'] = datetime.now().isoformat()

    # Save to ranking_unselected_data.json
    with open(export_path / 'ranking_unselected_data.json', 'w') as f:
        json.dump(ranking_data, f, indent=2)

    return jsonify({'success': True})


@app.route('/api/get_utility_viz', methods=['POST'])
def get_utility_viz():
    """Get utility visualization data for real-time tracking during study."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]

    # Only provide data if using BALD algorithm
    if not session.get('use_bald', False):
        return jsonify({
            'success': True,
            'has_data': False
        })

    selector = session['selector']

    # Check if we have enough data (after burn-in)
    # BALD requires at least 10 comparisons before GPPL model is fitted
    if len(selector.comparisons) < 10:
        return jsonify({
            'success': True,
            'has_data': False
        })

    # Check if model has been fitted
    if not hasattr(selector, 'model') or selector.model is None:
        return jsonify({
            'success': True,
            'has_data': False
        })

    try:
        image_ids = session['image_ids']

        # Build timeline from tracking data and get top from latest iteration
        timeline = []
        latest_top_idx = None

        if hasattr(selector, 'tracking_data'):
            tracking = selector.tracking_data
            utilities_history = tracking.get('utilities_per_iteration', [])

            prev_top_idx = None
            for i, utils in enumerate(utilities_history):
                if len(utils) > 0:
                    max_util = float(np.max(utils))
                    mean_util = float(np.mean(utils))
                    iter_top_idx = int(np.argmax(utils))

                    top_changed = (prev_top_idx is not None and
                                 iter_top_idx != prev_top_idx)

                    timeline.append({
                        'max_utility': max_util,
                        'mean_utility': mean_util,
                        'top_changed': top_changed
                    })

                    prev_top_idx = iter_top_idx
                    latest_top_idx = iter_top_idx  # Use top from this iteration

        # Fallback to get_utilities if no tracking data
        if latest_top_idx is None:
            utilities = selector.get_utilities()
            if utilities is None or len(utilities) == 0:
                return jsonify({'success': True, 'has_data': False})
            latest_top_idx = int(np.argmax(utilities))

        top_image_id = image_ids[latest_top_idx]
        top_image_path = f"/images/{top_image_id}"

        return jsonify({
            'success': True,
            'has_data': True,
            'timeline': timeline,
            'top_image': {
                'id': top_image_id,
                'path': top_image_path
            }
        })

    except Exception as e:
        print(f"Error generating utility viz: {e}")
        return jsonify({
            'success': True,
            'has_data': False
        })


@app.route('/api/save_prolific_id', methods=['POST'])
def save_prolific_id():
    """Save Prolific ID mapping to session ID and backup to S3."""
    data = request.json
    session_id = data.get('session_id')
    prolific_id = data.get('prolific_id', '').strip()
    study_code = data.get('study_code')  # one, two, three

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    if not prolific_id:
        return jsonify({'error': 'Prolific ID is required'}), 400

    # Save to global prolific mapping file
    mapping_path = Path('data_exports') / 'prolific_mapping.csv'
    file_exists = mapping_path.exists()

    with open(mapping_path, 'a', newline='') as f:
        fieldnames = ['session_id', 'prolific_id', 'timestamp', 'study_code']
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            'session_id': session_id,
            'prolific_id': prolific_id,
            'timestamp': datetime.now().isoformat(),
            'study_code': study_code or ''
        })

    # Backup session data to S3 (study=three goes to /researcher/, others to /participant/)
    backup_session_to_s3(session_id, study_code)

    return jsonify({'success': True})


@app.route('/api/submit_timing_stats', methods=['POST'])
def submit_timing_stats():
    """Receive and log pair loading time statistics."""
    data = request.json
    session_id = data.get('session_id')

    if session_id not in sessions:
        return jsonify({'error': 'Invalid session'}), 400

    session = sessions[session_id]
    export_path = Path(session['export_path'])

    # Save timing stats to file
    timing_path = export_path / 'pair_loading_times.json'
    with open(timing_path, 'w') as f:
        json.dump(data, f, indent=2)

    # Print statistics to console
    print("\n" + "="*50)
    print("PAIR LOADING TIME STATISTICS")
    print("="*50)
    print(f"Session ID: {session_id}")
    print(f"Participant: {session['participant_id']}")
    print(f"-" * 50)
    print(f"Mean:  {data.get('mean')}ms")
    print(f"Std:   {data.get('std')}ms")
    print(f"Min:   {data.get('min')}ms")
    print(f"Max:   {data.get('max')}ms")
    print(f"Count: {data.get('count')} pairs")
    print("="*50 + "\n")

    return jsonify({'success': True})


if __name__ == '__main__':
    # Ensure data exports directory exists
    Path(CONFIG['DATA_EXPORTS_PATH']).mkdir(parents=True, exist_ok=True)

    print(f"Starting WikiArt Preference Study Platform")
    print(f"  Practice trials: {CONFIG['N_PRACTICE_TRIALS']}")
    print(f"  Main trials: {CONFIG['N_MAIN_TRIALS']}")
    print(f"  Algorithm: {CONFIG['ALGORITHM']}")
    print(f"  Recommender: {CONFIG['RECOMMENDER']}")

    # Use PORT from environment (Railway) or default to 5001
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
