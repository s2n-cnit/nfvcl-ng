from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic import computed_field
from models.base_model import NFVCLBaseModel


class HelmRepo(NFVCLBaseModel):
    name: str
    description: str
    version: str

class HelmChart(NFVCLBaseModel):
    name: str
    version: str
    created: str = Field(default=datetime.utcnow().replace(microsecond=0).isoformat()+'Z')
    digest: Optional[str]
    home: str = Field(default='https://helm.sh/helm')
    sources: List[str] = Field(default=['https://github.com/helm/helm'])
    urls: List[str]

    def get_filename(self):
        return f'{self.name}-{self.version}.tgz'

    @computed_field
    @property
    def description(self) -> str:
        return f'Helm package for {self.name} version {self.version}'

class HelmIndex(NFVCLBaseModel):
    apiVersion: str = 'v1'
    entries: dict = Field(default={})
    generated: str = datetime.utcnow().replace(microsecond=0).isoformat()+'Z'

    @classmethod
    def build_index(cls, chart_list: List[HelmChart]):
        helm_index = HelmIndex()
        # Each entry need to have as key the name of the package. Using dictionaries is easier.
        for chart in chart_list:
            # A package can have different versions. If already present we add to the list, otherwise we create the list
            if chart.name in helm_index.entries:
                helm_index.entries[chart.name].append(chart)
            else:
                helm_index.entries[chart.name] = [chart]
        return helm_index
