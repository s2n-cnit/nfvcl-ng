#!/usr/bin/python3

from main import *
from fastapi import FastAPI
from rest_endpoints.topology import topology_router
from rest_endpoints.blue import blue_router
from rest_endpoints.day2action import day2_router
from rest_endpoints.k8s import k8s_router
from fastapi.staticfiles import StaticFiles


logger = create_logger('NFVCL')

"""
previous Flask rest classes:

api.add_resource(nsiAPI, '/nfvcl/api/nsi')
api.add_resource(vnfiAPI, '/nfvcl/api/vnfi')
api.add_resource(pduAPI, '/nfvcl/api/pdu')
api.add_resource(pnfAPI, '/nfvcl/api/pnf')
api.add_resource(vimAPI, '/nfvcl/api/vim')
# api.add_resource(k8sAPI, '/nfvcl/api/k8s')
api.add_resource(UeDbAPI, '/nfvcl/api/uedb')
api.add_resource(BluetypeAPI, '/nfvcl/api/bluetype')
api.add_resource(BlueMetrics, '/nfvcl/bluemetrics')

api.add_resource(VoApi, '/nfvcl/vo')  # /<string:arg>
"""


app = FastAPI(
    title="NFVCL",
    # description=description,
    version="0.0.1",
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)

app.include_router(topology_router)
app.include_router(blue_router)
app.include_router(day2_router)
app.include_router(k8s_router)
app.mount("/nfvcl_day2/day2", StaticFiles(directory="day2_files"), name="day2_files")
app.mount("/helm_repo", StaticFiles(directory="helm_charts"), name="helm_repo")

# if __name__ == '__main__':

