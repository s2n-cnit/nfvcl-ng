# Docker

<!-- TOC -->
* [Docker](#docker)
  * [Requirements](#requirements)
  * [Running alone mounting configuration files](#running-alone-mounting-configuration-files)
  * [Running alone using environment variables](#running-alone-using-environment-variables)
  * [Running with Docker compose](#running-with-docker-compose)
    * [Docker Compose files](#docker-compose-files)
    * [Running](#running)
    * [Build the application locally](#build-the-application-locally)
  * [Swagger / APIs list](#swagger--apis-list)
<!-- TOC -->

## Requirements
- Have Docker installed and running

## Running alone mounting configuration files
Using the Docker compose file as a reference:

``` yaml
...
  nfvcl:
    image: registry.tnt-lab.unige.it/nfvcl/nfvcl-ng:latest
    depends_on:
      - mongo
      - redis
    restart: always
    ports:
      - 5002:5002
    volumes:
      - ./config/config_compose.yaml:/app/nfvcl-ng/config/config.yaml
      - ./logs/:/app/nfvcl-ng/logs/
...
```
Then we can start the container with:

> **Note:** You should change values in the config_compose.yaml file to match your environment.

``` bash
docker run -d \
  --name nfvcl \
  --restart always \
  -p 5002:5002 \
  -v ./config/config_compose.yaml:/app/nfvcl-ng/config/config.yaml \
  -v ./logs/:/app/nfvcl-ng/logs/ \
  registry.tnt-lab.unige.it/nfvcl/nfvcl-ng:latest
```

## Running alone using environment variables

Usually you will need to mount the configuration file and the logs to keep track of the activities.
It is also possible to use environment variables to overwrite the default configuration or the mounted one.
ENV parameters, with values examples, that can be used are:

```
docker run -d \  
  --name nfvcl \
  --restart always \
  -p 6589:6589 \
  -e MONGO_IP=192.168.255.100 \
  -e MONGO_PORT=27017 \
  -e MONGO_PWD=password \
  -e MONGO_USR=admin \
  -e NFVCL_PORT=6589 \
  -e NFVCL_IP=0.0.0.0 \
  -e REDIS_IP=192.168.255.100 \
  -e REDIS_PORT=6379 \
  -e REDIS_PASSWORD=password \
  -v ./logs/:/app/nfvcl-ng/logs/ \
  registry.tnt-lab.unige.it/nfvcl/nfvcl-ng:dev
```



## Running with Docker compose
### Docker Compose files
- The `stable` one (`compose-stable.yaml`), updated less frequently but should not include unstable features.
- The `master` (`compose.yaml`) is updated as soon as a cycle of improvements has been made and partially tested
- The `latest` (`compose-latest.yaml`) branch is the one updated as soon as new features/fix are implemented. 
- The `latest` (`compose-dev.yaml`) It is the branch used for development.
- The `build` (`compose-build.yaml`) is the one used to build the application locally on the branch you have downloaded.

### Running

```{image} ../images/NVFCL-diagrams-DockerCompose.drawio.svg
:alt: Docker topology
:width: 400px
:align: center
```

Clone the repo:
``` bash
git clone --depth 1 https://github.com/s2n-cnit/nfvcl-ng
```
Then run `docker compose up` for starting the 3 containers needed
``` bash
➜  nfvcl-ng git:(master) ✗ docker compose up -d
[+] Running 3/3
 ✔ Container nfvcl-ng-redis-1  Started                                                                                                                                                                                                                                                                                                                     0.5s 
 ✔ Container nfvcl-ng-mongo-1  Started                                                                                                                                                                                                                                                                                                                     0.4s 
 ✔ Container nfvcl-ng-nfvcl-1  Started     
```
To get a summary of the topology and see the list of containers:
```
➜  nfvcl-ng git:(master) ✗ docker ps
CONTAINER ID   IMAGE                                                    COMMAND                  CREATED         STATUS              PORTS                                           NAMES
9a748ec9ee0c   registry.tnt-lab.unige.it/nfvcl/nfvcl-ng:latest          "/root/.local/bin/po…"   2 minutes ago   Up About a minute   0.0.0.0:5002->5002/tcp, :::5002->5002/tcp       nfvcl-ng-nfvcl-1
02528ee4b0b3   mongo                                                    "docker-entrypoint.s…"   2 minutes ago   Up About a minute   0.0.0.0:27017->27017/tcp, :::27017->27017/tcp   nfvcl-ng-mongo-1
31472b7cf98b   redis:alpine                                             "docker-entrypoint.s…"   2 minutes ago   Up About a minute   0.0.0.0:6379->6379/tcp, :::6379->6379/tcp       nfvcl-ng-redis-1
```

As you can see from the list, these 3 containers are exposed on every interface of the server on which Docker is running.

If one or more containers does not start or crashes, you can analyze logs to see what is happening:

```
➜  nfvcl-ng git:(master) ✗ docker logs 9a748ec9ee0c
The currently activated Python version 3.10.12 is not supported by the project (^3.11).
Trying to find and use a compatible version. 
Using python3.11 (3.11.9)
2024-06-25 09:37:30 [PreConfig           ][MainThread] [    INFO] [SYSTEM] Loading config from config.yaml

...

INFO:     Waiting for application startup.
2024-06-25 09:37:46 [uvicorn.error       ][MainThread] [    INFO] [SYSTEM] Application startup complete.
2024-06-25 09:37:46 [uvicorn.error       ][MainThread] [    INFO] [SYSTEM] Uvicorn running on http://10.224.52.4:5002 (Press CTRL+C to quit)
```

### Build the application locally

> **Important:** Building from source requires generating a version file before the Docker build, since the `.git` folder is excluded from Docker images. Use the provided helper scripts to automate this process.

#### Using the Helper Script (Recommended)

The easiest way to build locally is using the provided helper script:

```bash
git clone https://github.com/s2n-cnit/nfvcl-ng.git
cd nfvcl-ng
# OPTIONAL: change to the desired branch
git checkout <branch-name>

# Build and start with docker-compose
./scripts/compose_build.sh docker-compose/compose-build.yaml up --build -d
```

The script automatically:
1. Generates the version file from git tags
2. Builds the Docker image
3. Starts the containers

#### Manual Build (Two-Step Process)

If you prefer to build manually:

```bash
git clone https://github.com/s2n-cnit/nfvcl-ng.git
cd nfvcl-ng

# Step 1: Generate version file from git tags
python3 scripts/generate_version.py

# Step 2: Build and start with docker-compose
docker compose -f docker-compose/compose-build.yaml up --build -d
```

#### Updating the Local Application

To update and rebuild the application:

```bash
git pull

# Regenerate version file (in case tags changed)
python3 scripts/generate_version.py

# Rebuild and restart
docker compose -f docker-compose/compose-build.yaml down
docker compose -f docker-compose/compose-build.yaml build --no-cache
docker compose -f docker-compose/compose-build.yaml up -d
```

Or use the helper script:

```bash
git pull
./scripts/compose_build.sh docker-compose/compose-build.yaml up --build -d
```

#### Building Direct Docker Image (Without Compose)

To build a standalone Docker image:

```bash
# Using the build script (recommended)
./scripts/build_docker.sh nfvcl-local

# Or manually
python3 scripts/generate_version.py
docker build -t nfvcl-local .
```

#### Version Management

This project uses git tags as the single source of truth for versioning. The version is automatically derived from git tags using `hatch-vcs`.

- When building locally, a version file (`src/nfvcl/_version.py`) must be generated before the Docker build
- The version file is created from the latest git tag (e.g., `v0.4.1`)
- If you're between tags, the version includes development metadata (e.g., `0.4.1.dev5+g1234abc`)

For more details on version management, see `scripts/README.md`.

#### Troubleshooting

**Error: "src/nfvcl/_version.py not found"**

This means you tried to build without generating the version file first.

Solution:
```bash
python3 scripts/generate_version.py
```

Then retry the build.

**Error: "git describe failed"**

You don't have any git tags in your repository. Create one:
```bash
git tag v0.4.1
```

## Swagger / APIs list
Suppose that the server on which containers are running as an IP that is `IP.OF.VM_OR.PC`
To access and try APIs, you can use the Swagger that contains a list of available APIs: http://IP.OF.VM_OR.PC:5002/docs (replace IP.OF.VM_OR.PC with the IP of the server)

