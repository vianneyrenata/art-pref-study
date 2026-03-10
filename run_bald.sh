#!/bin/bash
# Run experiment with BALD (Bayesian Active Learning by Disagreement)

echo "=========================================="
echo "  Starting BALD Algorithm Experiment"
echo "=========================================="
echo ""
echo "Settings:"
echo "  - Algorithm: BALD (active learning)"
echo "  - Dataset: pilot-400 (400 images)"
echo "  - Practice trials: 3"
echo "  - Main trials: 110 (10 random burn-in + 100 BALD)"
echo "  - Surveys: Every 10 trials"
echo "  - PCA dimensions: 10"
echo "  - Recommender: utility-based"
echo ""
echo "Setting up config..."

# Copy BALD config to active config
cp config_bald.json config.json

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
