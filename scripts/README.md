# Build Scripts

## Version Management

This project uses git tags as the single source of truth for versioning. The version is automatically derived from git tags using `hatch-vcs`.

### For Local Development

When developing locally with git available, the version is automatically detected from git tags. No manual steps needed.

### For Docker Builds

Docker builds **require** a pre-generated version file since `.git` folder is not copied into the container.

#### Local Docker Build

Use the provided build script:

```bash
./scripts/build_docker.sh [image-name]
```

This script will:
1. Generate `src/nfvcl/_version.py` from git tags
2. Build the Docker image
3. Tag it with the specified name (default: `nfvcl`)

#### Manual Docker Build

If you need to build manually:

```bash
# Step 1: Generate version file
python3 scripts/generate_version.py

# Step 2: Build Docker image
docker build -t nfvcl .
```

#### Docker Compose Build

For docker-compose builds (e.g., `docker-compose/compose-build.yaml`):

```bash
# Using the helper script (recommended)
./scripts/compose_build.sh docker-compose/compose-build.yaml up --build

# Or generate version manually, then build
python3 scripts/generate_version.py
docker compose -f docker-compose/compose-build.yaml up --build
```

### For CI/CD (GitLab)

The `.gitlab-ci.yml` automatically generates the version file before building:

```yaml
before_script:
  - python3 scripts/generate_version.py
```

### Creating New Releases

To create a new release:

```bash
# Tag the release (use semantic versioning)
git tag v0.5.0

# Push the tag
git push origin v0.5.0
```

The version will automatically be used in:
- Package metadata
- Documentation (Sphinx)
- Docker builds

### Version File

- **File**: `src/nfvcl/_version.py`
- **Status**: Auto-generated, in `.gitignore`
- **Purpose**: Fallback for environments without git

### Troubleshooting

**Error: "src/nfvcl/_version.py not found"**

This means you tried to build Docker without generating the version file first.

Solution:
```bash
python3 scripts/generate_version.py
```

**Error: "git describe failed"**

You don't have any git tags. Create one:
```bash
git tag v0.4.1
```
