#!/bin/bash
# Run experiment with RANDOM pair selection

echo "=========================================="
echo "  Starting RANDOM Algorithm Experiment"
echo "=========================================="
echo ""
echo "Settings:"
echo "  - Algorithm: Random pair selection"
echo "  - Dataset: pilot-400 (400 images)"
echo "  - Practice trials: 3"
echo "  - Main trials: 110"
echo "  - Surveys: Every 10 trials"
echo "  - Recommender: embedding-based"
echo ""
echo "Setting up config..."

# Copy random config to active config
cp config_random.json config.json

echo "✓ Config loaded"
echo ""
echo "Optimizing system performance..."

# Clear Python bytecode cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

echo "✓ Cleared Python cache"

# Note: To clear system cache (requires sudo), run:
# sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'

echo ""
echo "Starting Flask server with high priority..."
echo "Open: http://localhost:5001"
echo ""
echo "=========================================="
echo ""

# Run the app with nice priority (lower value = higher priority)
python3 app.py
