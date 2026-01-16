#!/bin/bash
# Build Docker image with proper version handling
#
# Usage: ./scripts/build_docker.sh [image-name]
#
# This script:
# 1. Generates src/nfvcl/_version.py from git tags
# 2. Builds the Docker image
# 3. Cleans up the generated version file (optional)

set -e  # Exit on error

IMAGE_NAME="${1:-nfvcl}"

echo "=========================================="
echo "Building Docker image: $IMAGE_NAME"
echo "=========================================="

# Step 1: Generate version file
echo ""
echo "Step 1: Generating version file from git..."
python3 scripts/generate_version.py

if [ ! -f "src/nfvcl/_version.py" ]; then
    echo "ERROR: Failed to generate version file"
    exit 1
fi

# Step 2: Build Docker image
echo ""
echo "Step 2: Building Docker image..."
docker build -t "$IMAGE_NAME" .

# Optional: Clean up generated file (uncomment if desired)
# echo ""
# echo "Step 3: Cleaning up generated version file..."
# rm -f src/nfvcl/_version.py

echo ""
echo "=========================================="
echo "✓ Docker image built successfully: $IMAGE_NAME"
echo "=========================================="
