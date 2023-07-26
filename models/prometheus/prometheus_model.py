from pydantic import BaseModel, Field
from typing import List


class PrometheusTargetModel(BaseModel):
    targets: List[str]
    labels: dict


class PrometheusServerModel(BaseModel):
    id: str
    ip: str
    port: str
    user: str
    password: str
    jobs: List[PrometheusTargetModel] = Field(default=[], description="The list of jobs currenctly active on the"
                                                                      "prometheus server.")
    sd_file_location: str = Field(default="/etc/prometheus/sd_targets.yml", description="The location of the sd_file"
                                  "witch contains dynamic target of the prometheus server")
