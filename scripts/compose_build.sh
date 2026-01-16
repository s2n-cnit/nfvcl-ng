#!/bin/bash
# Docker Compose build helper - generates version file before building
#
# Usage:
#   ./scripts/compose_build.sh [compose-file] [additional docker-compose args...]
#
# Examples:
#   ./scripts/compose_build.sh docker-compose/compose-build.yaml
#   ./scripts/compose_build.sh docker-compose/compose-build.yaml up -d
#   ./scripts/compose_build.sh docker-compose/providers_rest/compose-build.yaml up --build

set -e  # Exit on error

# Check if compose file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <compose-file> [docker-compose-args...]"
    echo ""
    echo "Examples:"
    echo "  $0 docker-compose/compose-build.yaml"
    echo "  $0 docker-compose/compose-build.yaml up -d"
    echo "  $0 docker-compose/compose-build.yaml up --build"
    exit 1
fi

COMPOSE_FILE="$1"
shift  # Remove first argument, rest are docker-compose args

# Validate compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "ERROR: Compose file not found: $COMPOSE_FILE"
    exit 1
fi

echo "=========================================="
echo "Docker Compose Build Helper"
echo "=========================================="
echo "Compose file: $COMPOSE_FILE"
echo ""

# Step 1: Generate version file
echo "Step 1: Generating version file from git..."
python3 scripts/generate_version.py

if [ ! -f "src/nfvcl/_version.py" ]; then
    echo "ERROR: Failed to generate version file"
    exit 1
fi

# Step 2: Run docker-compose with the provided arguments
echo ""
echo "Step 2: Running docker-compose..."
if [ $# -eq 0 ]; then
    # No additional args, just build
    docker compose -f "$COMPOSE_FILE" build
else
    # Pass through all additional arguments
    docker compose -f "$COMPOSE_FILE" "$@"
fi

echo ""
echo "=========================================="
echo "✓ Docker Compose command completed"
echo "=========================================="
