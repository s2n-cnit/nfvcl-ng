# Configuration file

```
---
log_level: "20"      # 10 = DEBUG, CRITICAL = 50,FATAL = CRITICAL, ERROR = 40, WARNING = 30, WARN = WARNING, INFO = 20, DEBUG = 10, NOTSET = 0
nfvcl: 
  version: "0.3.0"
  port: "5002"
  ip: ""    # Empty takes the default network interface
mongodb: 
  host: "127.0.0.1"
  port: "27017"
  db: "nfvcl"
  username: "admin"  # OPTIONAL
  password: "password" # OPTIONAL
redis: 
  host: "127.0.0.1"
  port: "6379"
```

# Configuration using ENV variables
Using ENV variables every value loaded from the configuration file will be overwritten, this means that you can override
alse a single value.

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
