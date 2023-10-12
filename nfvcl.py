#!/usr/bin/python3
# DO NOT MOVE THIS PIECE OF CODE -------
# Log level must be set before loggers are created!
from utils.log import mod_logger, set_log_level
from utils.util import get_nfvcl_config

_nfvcl_config = get_nfvcl_config()
set_log_level(_nfvcl_config.log_level)
# DO NOT MOVE THIS PIECE OF CODE -------

from starlette import status
import rest_endpoints.blue
import logging
import signal
import os
from fastapi import FastAPI
from rest_endpoints.rest_callback import RestAnswer202
from rest_endpoints.topology import topology_router
from rest_endpoints.blue import blue_router
from rest_endpoints.day2action import day2_router
from rest_endpoints.k8s import k8s_router
from rest_endpoints.helm import helm_router
from fastapi.staticfiles import StaticFiles
from rest_endpoints.osm_rest import osm_router



app = FastAPI(
    title="NFVCL",
    # description=description,
    version="0.0.1",
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)

# Populate blue_router with all blueprints APIs before include it.
rest_endpoints.blue.initialize_blueprints_routers()

# Including routers for each case. In this part all APIs definitions are loaded.
app.include_router(topology_router)
app.include_router(blue_router)
app.include_router(day2_router)
app.include_router(k8s_router)
app.include_router(helm_router)
app.include_router(osm_router)

day2_files = "day2_files"

# Check if the day2 folder exists and, in case not, it creates the folder.
if not os.path.exists(day2_files):
    os.makedirs(day2_files)

# Making repositories available for external access. Configuration files will be served from here.
app.mount("/nfvcl_day2/day2", StaticFiles(directory="day2_files"), name="day2_files")
app.mount("/helm_repo", StaticFiles(directory="helm_charts"), name="helm_repo")


@app.post("/close", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def close_nfvcl():
    """
    Terminate the NFVCL.
    """
    os.kill(os.getpid(), signal.SIGTERM)
    return RestAnswer202(id="close", description="Closing")


@app.on_event("startup")
async def startup_event():
    logger1 = logging.getLogger('uvicorn.access')
    logger2 = logging.getLogger('uvicorn.error')
    mod_logger(logger1)
    mod_logger(logger2)
