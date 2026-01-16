# Launching the application using Docker Compose

To launch the application using Docker Compose, you need to have Docker and Docker Compose installed on your machine. If you don't have them installed, you can follow the instructions on the [official Docker website](https://docs.docker.com/get-docker/).

Once you have Docker and Docker Compose installed, you can run the following command to launch the application:

> **Warning:** You should choose the appropriate Docker Compose file based on your requirements. See the [Docker Compose files](#docker-compose-files) section for more information.

> **Warning:** You might use `docker-compose` instead of `docker compose` depending on your Docker Compose version.

To start the application, run the following command:
```bash
docker compose -f compose.yaml up -d
```
To stop the application, run the following command:
```bash
docker compose -f compose.yaml down
```

## Docker Compose files
- The `stable` one (`compose-stable.yaml`), updated less frequently but should not include unstable features.
- The `master` (`compose.yaml`) is updated as soon as a cycle of improvements has been made and partially tested
- The `dev` (`compose-latest.yaml`) branch is the one updated as soon as new features/fix are implemented. It is the branch used for development.
- The `build` (`compose-build.yaml`) is the one used to build the application locally on the branch you have downloaded.

## Building from Source (compose-build.yaml)

**IMPORTANT**: When using `compose-build.yaml`, you must generate the version file first because the `.git` folder is not included in Docker builds.

### Recommended Method - Using Helper Script

```bash
# From project root
./scripts/compose_build.sh docker-compose/compose-build.yaml up --build
```

### Manual Method

```bash
# Step 1: Generate version file (from project root)
python3 scripts/generate_version.py

# Step 2: Build and run with docker-compose
docker compose -f docker-compose/compose-build.yaml up --build
```

### Why is this needed?

The Docker build process requires `src/nfvcl/_version.py` to exist because:
- The `.git` folder is excluded from Docker builds (see `.dockerignore`)
- The build system (`hatch-vcs`) needs either git or a pre-generated version file
- The version file must be created **before** running `docker compose build`

For more details on version management, see `scripts/README.md`.
