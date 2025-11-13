from typing import List, Optional

from pydantic import BaseModel, Field

from nfvcl_common.utils.blue_utils import yaml
from nfvcl_common.utils.file_utils import create_tmp_file
from nfvcl_common.utils.util import generate_id
from nfvcl_core_models.network.ipam_models import EndPointV4


class PrometheusTargetModel(BaseModel):
    """
    Models a target for a Prometheus server.
    """
    id: str = Field(default_factory=generate_id)
    endpoints: List[EndPointV4] = Field(default=[], description="List of targets to be scraped by the prometheus server (e.g. ['192.168.1.4:9100'])")
    labels: dict = Field(default={})

    def __eq__(self, other):
        if isinstance(other, PrometheusTargetModel):
            return self.id == other.id
        return False

class PrometheusServerModel(BaseModel):
    """
    Models a Prometheus server instance to be managed.
    """
    id: str
    ip: str = Field(default='127.0.0.1')
    port: str = Field(default='9090')
    user: str = Field(default='ubuntu')
    password: str = Field(default='ubuntu')
    ssh_port: int = Field(default=22)
    targets: List[PrometheusTargetModel] = Field(default=[], description="List of targets and labels to be inserted in sd_file such that prometheus start collecting data from this target.")
    sd_file_location: str = Field(default="sd_targets.yml", description="The location (relative to HOME or the global path) of the sd_file witch contains dynamic target of the prometheus server")

    def serialize_for_prometheus(self):
        prom_targets = []
        for target in self.targets:
            serialized: dict = {"labels": target.labels}
            endpoints_list = [str(endpoint) for endpoint in target.endpoints]
            serialized["targets"] = endpoints_list
            prom_targets.append(serialized)
        return prom_targets

    def add_target(self, new_target: PrometheusTargetModel):
        """
        If the target is NOT present in any job, it creates a new job with the new target. Otherwise, it updates
        the existing target inside the relative job
        Args:
            new_target: The target to be added for scraping
        """
        # For all existing jobs, we check that there isn't already a target corresponding to the one to be added
        conflicting_targets = False
        for current_target in self.targets:
            indexes = (index for index, current_target_ip in enumerate(current_target.endpoints) if current_target_ip in new_target.endpoints)
            existing_target_index = next(indexes, None)
            # If the target is already present, we update the labels with the current one
            if existing_target_index is not None:
                existing_target = self.targets[existing_target_index]
                existing_target.labels = new_target.labels
                conflicting_targets = True
                break

        # In case there is NOT an existing job with the target to be added, we create a new job containing the new target.
        if not conflicting_targets:
            self.targets.append(new_target)

    def add_targets(self, targets: List[PrometheusTargetModel]):
        """
        Add targets to be scraped by the server
        Args:
            targets: The target list to be added for scraping
        """
        for target in targets:
            self.add_target(target)

    def find_target_by_endpoint(self, endpoint: EndPointV4) -> PrometheusTargetModel:
        """
        Returns the target given an ip address (ipaddress:port)
        Args:
            endpoint: the endpoint used to find the target

        Returns:
            The target if it has been found or None
        """
        return next((target for target in self.targets if endpoint in target.endpoints), None)

    def find_job_by_labels(self, label) -> PrometheusTargetModel:
        """
        Returns the FIRST target given a label
        Args:
            label: the label used to find the target

        Returns:
            The target if it has been found or None
        """
        return next((target for target in self.targets if label in target.labels), None)

    def del_endpoint_from_target(self, endpoint: EndPointV4) -> Optional[PrometheusTargetModel]:
        """
        Removes a specified endpoint from the target list (First one is removed). If the endpoint is found
        and removed, the FIRST corresponding target is returned. If the endpoint is not
        found in any target, returns None.

        Args:
            endpoint: The endpoint to be removed from the targets.

        Returns:
            The PrometheusTargetModel from which the endpoint was removed, or
            None if the endpoint was not found in any target.
        """
        for target in self.targets:
            if endpoint in target.endpoints:
                target.endpoints.remove(endpoint)
                return target
        return None

    def del_targets(self, targets: List[PrometheusTargetModel]):
        """
        Add (sub) jobs to be scraped by the server
        Args:
            targets: The target list to be added for scraping
        """
        for target in targets:
            self.targets.remove(target)

    def dump_sd_file(self) -> str:
        """
        Create a local copy (on the host running NFVCL) of the sd_file to be uploaded on the Prometheus server.
        Returns:
            The path of the created file.
        """
        relative_path = create_tmp_file("prometheus", f"prometheus_{self.id}_scraps.yaml", file_can_exist=True)
        # relative_path: str = 'day2_files/prometheus_{}_scraps.yaml'.format(self.id)
        with relative_path.open("+w") as file:
            file.write(yaml.dump(self.serialize_for_prometheus()))
        return str(relative_path.absolute())

    def __eq__(self, other):
        """
        Overrides the default equals implementation.
        In this way, it is possible to directly compare objects
        of this type on a given criteria (in this case the id)
        """
        if isinstance(other, PrometheusServerModel):
            return self.id == other.id
        return False
