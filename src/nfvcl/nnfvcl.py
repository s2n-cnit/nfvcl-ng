#!/usr/bin/python3
# DO NOT MOVE THIS PIECE OF CODE -------
# Log level must be set before loggers are created!
# import nfvcl.rest_endpoints.blue
from nfvcl.rest_endpoints.ansible import ansible_router
from nfvcl.rest_endpoints.blue import blue_router
from nfvcl.rest_endpoints.day2action import day2_router
from nfvcl.rest_endpoints.helm import helm_router
from nfvcl.rest_endpoints.k8s import k8s_router
from nfvcl.rest_endpoints.openstack import openstack_router
from nfvcl.rest_endpoints.osm_rest import osm_router
from nfvcl.rest_endpoints.rest_callback import RestAnswer202
from nfvcl.rest_endpoints.topology import topology_router
from nfvcl.rest_endpoints.blue_ng_router import blue_ng_router as blue_ng_router2
from nfvcl.rest_endpoints.horse import horse_router

from nfvcl.rest_endpoints import blue, blue_ng_router
from nfvcl.utils.log import mod_logger, set_log_level
from nfvcl.utils.util import get_nfvcl_config

_nfvcl_config = get_nfvcl_config()
set_log_level(_nfvcl_config.log_level)
# DO NOT MOVE THIS PIECE OF CODE -------

from starlette import status
import logging
import signal
import os
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

swagger_parameters={"syntaxHighlight.theme": "obsidian", "deepLinking": True}
app = FastAPI(
    title="NFVCL",
    description="CNIT/UniGe S2N Lab NFVCL",
    version=_nfvcl_config.nfvcl.version,
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    swagger_ui_parameters = swagger_parameters
)

# Populate blue_router with all blueprints APIs before include it.
blue.initialize_blueprints_routers()
blue_ng_router.get_blueprint_manager()

# Including routers for each case. In this part all APIs definitions are loaded.
app.include_router(topology_router)
app.include_router(blue_router)
app.include_router(blue_ng_router2)
app.include_router(day2_router)
app.include_router(k8s_router)
app.include_router(helm_router)
app.include_router(osm_router)
app.include_router(openstack_router)
app.include_router(ansible_router)
app.include_router(horse_router)

day2_files = "day2_files"

# Check if the day2 folder exists and, in case not, it creates the folder.
if not os.path.exists(day2_files):
    os.makedirs(day2_files)

# Making repositories available for external access. Configuration files will be served from here.
app.mount("/nfvcl_day2/day2", StaticFiles(directory="day2_files"), name="day2_files")
app.mount("/helm_repo", StaticFiles(directory="helm_charts"), name="helm_repo")


@app.get("/", status_code=status.HTTP_308_PERMANENT_REDIRECT)
async def redirect_to_swagger():
    """
    Redirect to docs page for APIs
    """
    return RedirectResponse("/docs")

@app.post("/close", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def close_nfvcl():
    """
    Terminate the NFVCL.
    """
    os.kill(os.getpid(), signal.SIGTERM)
    return RestAnswer202(id="close", description="Closing")


@app.on_event("startup")
async def startup_event():
    """
    Mod the unicorn loggers to add colors and custom style
    """
    mod_logger(logging.getLogger('uvicorn'))
    mod_logger(logging.getLogger('uvicorn.access'))
    mod_logger(logging.getLogger('uvicorn.error'))
    mod_logger(logging.getLogger('fastapi'))
