import os

from pydantic import BaseModel, Field
from typing import List
from utils.ssh_utils import upload_file, createSCPClient
import ruamel.yaml


class PrometheusTargetModel(BaseModel):
    """
    Models a target for a Prometheus server.
    """
    targets: List[str] = Field(default=[])
    labels: dict = Field(default={})


class PrometheusServerModel(BaseModel):
    """
    Models a Prometheus server instance to be managed.
    """
    id: str
    ip: str = Field(default='127.0.0.1')
    port: str = Field(default='9100')
    user: str = Field(default='ubuntu')
    password: str = Field(default='ubuntu')
    ssh_port: int = Field(default=22)
    targets: List[PrometheusTargetModel] = Field(default=[], description="List of targets and labels to be inserted in sd_file such that prometheus start collecting data from this target.")
    sd_file_location: str = Field(default="sd_targets.yml", description="The location (relative to HOME or the global path) of the sd_file witch contains dynamic target of the prometheus server")

    def add_target(self, new_target: PrometheusTargetModel):
        """\
        If the target is NOT present in any job, it creates a new job with the new target. Otherwise, it updates
        the existing target inside the relative job
        Args:
            new_target: The target to be added for scraping
            labels: Labels to be assigned at metrics coming from the target
        """
        # For all existing jobs, we check that there isn't already a target corresponding to the one to be added
        conflicting_targets = False
        for current_target in self.targets:
            indexes = (index for index, current_target_ip in enumerate(current_target.targets) if current_target_ip in new_target.targets)
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

    def find_target_by_ipaddress(self, ip_a: str) -> PrometheusTargetModel:
        """
        Returns the target given an ip address (ipaddress:port)
        Args:
            ip_a: the ip address used to find the target

        Returns:
            The target if it has been found or None
        """
        return next((job for job in self.targets if ip_a in job.targets), None)

    def find_job_by_labels(self, label) -> PrometheusTargetModel:
        """
        Returns the FIRST target given a label
        Args:
            label: the label used to find the target

        Returns:
            The target if it has been found or None
        """
        return next((target for target in self.targets if label in target.labels), None)

    def del_target(self, target_ip: PrometheusTargetModel) -> PrometheusTargetModel:
        """
        Delete (sub) job to be scraped by the server
        Args:
            target_ip: The target to be removed from scraping

        Returns:
            The deleted target
        """
        for ip in target_ip.targets:
            target_to_del = self.find_target_by_ipaddress(ip)
            if target_to_del is not None:
                index = self.targets.index(target_to_del)
                removed = self.targets.pop(index)
                return removed

        raise ValueError("Target to be delete has not been found")

    def del_targets(self, targets: List[PrometheusTargetModel]):
        """
        Add (sub) jobs to be scraped by the server
        Args:
            targets: The target list to be added for scraping
        """
        for target in targets:
            self.del_target(target)

    def dump_sd_file(self) -> str:
        """
        Create a local copy (on the host running NFVCL) of the sd_file to be uploaded on the Prometheus server.
        Returns:
            The path of the created file.
        """
        relative_path: str = 'day2_files/prometheus_{}_scraps.yaml'.format(self.id)
        with open(relative_path, 'w') as file:
            file.write(ruamel.yaml.dump(self.model_dump()['targets'], Dumper=ruamel.yaml.RoundTripDumper, allow_unicode=True))
        global_path = f"{os.getcwd()}/{relative_path}"
        return global_path

    def update_remote_sd_file(self):
        """
        Create or update the remote sd_file to be used by Prometheus to select targets
        """
        scp_client = createSCPClient(self.ip, self.ssh_port, self.user, self.password)
        upload_file(scp_client, self.dump_sd_file(), self.sd_file_location)

    def __eq__(self, other):
        """
        Overrides the default equals implementation.
        In this way, it is possible to directly compare objects
        of this type on a given criteria (in this case the id)
        """
        if isinstance(other, PrometheusServerModel):
            return self.id == other.id
        return False
