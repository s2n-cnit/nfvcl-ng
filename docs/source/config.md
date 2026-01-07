# Configuration
## Configuration file
NFVCL configuration can be done though the configuration file or using [ENV variables](config/config.md).
In production, it is suggested to change values in `config/config.yaml`, while, for developing you can create a copy of the default configuration and call it `config/config_dev.yaml`. 
When the NFVCL starts, it loads the configuration from `config/config_dev.yaml` if present, otherwise the configuration is loaded from the default file.


> :information_source: Redis and Mongo **IP** should be 127.0.0.1 if they are running on the same machine of NFVCL.

> :warning: Authentication is disabled by default, to enable it set `authentication: True` in the configuration file.
> Default user is `admin` and the password is `admin`

```
---
log_level: "20" # 20 is info, 10 is debug
nfvcl:
  port: "5002"
  ip: "0.0.0.0" # Listen on every interface
  authentication: False
mongodb:
  host: "127.0.0.1"
  port: "27017"
  db: "nfvcl"
#  username: "admin"
#  password: "password"
redis:
  host: "127.0.0.1"
  port: "6379"
```

## ENV variables
Using ENV variables every value loaded from the configuration file will be overwritten, this means that you can override
alse a single value.

The code expects `NFVCL_` prefix with nested structure using `_` delimiter. The nested structure is the same as the configuration file (see above)

```
NFVCL_MONGO_IP=127.0.0.1
NFVCL_MONGO_PORT=27017
NFVCL_MONGO_PWD=password
NFVCL_MONGO_USR=admin
NFVCL_PORT=6589
NFVCL_IP=0.0.0.0
NFVCL_REDIS_IP=127.0.0.1
NFVCL_REDIS_PORT=6379
```

### Example
```
 docker run -d \  
  --name nfvcl \
  --restart always \
  -p 6589:6589 \
  -e NFVCL_NFVCL_IP=0.0.0.0 \
  -e NFVCL_NFVCL_PORT=6589 \
  -e NFVCL_MONGODB_HOST=192.168.255.100 \
  -e NFVCL_MONGODB_PORT=27017 \
  -e NFVCL_MONGODB_USERNAME=admin \
  -e NFVCL_MONGODB_PASSWORD=testpassword \
  -e NFVCL_MONGODB_DB=nfvcl \
  -e NFVCL_REDIS_HOST=192.168.111.111 \
  -e NFVCL_REDIS_PORT=6379 \
  -e NFVCL_REDIS_PASSWORD=testPWD \
  -v ./logs/:/app/nfvcl-ng/logs/ \
  registry.tnt-lab.unige.it/nfvcl/nfvcl-ng:dev
```
