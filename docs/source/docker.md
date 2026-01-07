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

### Build the container locally
```bash
git clone https://github.com/s2n-cnit/nfvcl-ng.git
# OPTIONAL change to the desired branch
cd nfvcl-ng
cd docker-compose
docker compose -f compose-build.yaml up -d
```
To update the local application, run the following command:
```bash
git pull
docker compose -f compose-build.yaml down
docker compose -f compose-build.yaml build --no-cache
docker compose -f compose-build.yaml up
```

## Swagger / APIs list
Suppose that the server on which containers are running as an IP that is `IP.OF.VM_OR.PC`
To access and try APIs, you can use the Swagger that contains a list of available APIs: http://IP.OF.VM_OR.PC:5002/docs (replace IP.OF.VM_OR.PC with the IP of the server)

