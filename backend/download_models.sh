#!/bin/bash
# Download and extract model files for P&ID detection
# This script is used during Docker build to fetch models from GitHub releases

set -e

MODEL_DIR="${1:-/app/models}"
MODEL_URL="https://github.com/aws-solutions-library-samples/guidance-for-piping-and-instrumentation-diagrams-digitization-on-aws/releases/download/v1.0.0/model.tar.gz"

echo "=== P&ID Model Download Script ==="
echo "Target directory: $MODEL_DIR"

# Check if models already exist
if [ -f "$MODEL_DIR/frcnn_checkpoint_50000.pth" ] && [ -f "$MODEL_DIR/last-v9.ckpt" ]; then
    echo "Models already exist, skipping download."
    exit 0
fi

# Create models directory
mkdir -p "$MODEL_DIR"
cd "$MODEL_DIR"

echo "Downloading model files from AWS P&ID GitHub release..."
echo "URL: $MODEL_URL"

# Download with progress and retry
curl -L --retry 3 --retry-delay 5 -o model.tar.gz "$MODEL_URL"

echo "Extracting model files..."
tar -xzf model.tar.gz

# Verify extraction
if [ -f "frcnn_checkpoint_50000.pth" ] && [ -f "last-v9.ckpt" ]; then
    echo "✅ Models extracted successfully!"
    echo "Files:"
    ls -lh frcnn_checkpoint_50000.pth last-v9.ckpt
    
    # Clean up archive to save space
    rm -f model.tar.gz
    echo "✅ Cleaned up archive file"
else
    echo "❌ Error: Model files not found after extraction"
    exit 1
fi

echo "=== Model download complete ==="
