# Docker

## Requirements
- Have Docker installed and running

## Running alone
Using the Docker compose as reference:

```
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
```

Usually you will need to mount the configuration file and the logs to keep track of the activities.
It is also possible to use environment variables to overwrite the default configuration or the mounted one.
ENV parameters, with values examples, that can be used are:

```
MONGO_IP=127.0.0.1
MONGO_PORT=27017
MONGO_PWD=password
MONGO_USR=admin
NFVCL_PORT=6589
NFVCL_IP=0.0.0.0
REDIS_IP=127.0.0.1
REDIS_PORT=6379
```

## Running with Docker compose
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

## Swagger / APIs list
Suppose that the server on which containers are running as an IP that is `192.168.254.12`
To access and try APIs, you can use the Swagger that contains a list of available APIs: http://192.168.254.11:5002/docs
