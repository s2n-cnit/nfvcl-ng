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
    jobs: List[PrometheusTargetModel] = Field(default=[],
                                             description="List of targets and labels to be inserted in sd_file such"
                                                         " that prometheus start collecting data from this target.")
    sd_file_location: str = Field(default="sd_targets.yml", description="The location (IN THE HOME) of the sd_file"
                                  "witch contains dynamic target of the prometheus server")

    def add_job(self, target: str, labels: dict):
        """
        Add (sub) job to be scraped by the server
        Args:
            target: The target to be added for scraping
        """
        conflicting_targets = False
        for job in self.jobs:
            indexes = (index for index, current_target in enumerate(job.targets) if current_target == target)
            existing_target = next(indexes, None)
            if existing_target is not None:
                job = self.jobs[existing_target]
                job.labels = labels
                conflicting_targets = True
                break
        if not conflicting_targets:
            new_job: PrometheusTargetModel = PrometheusTargetModel()
            new_job.targets.append(target)
            new_job.labels.update(labels)
            self.jobs.append(new_job)

    def add_jobs(self, targets: List[str], labels: dict = None):
        """
        Add (sub) jobs to be scraped by the server
        Args:
            targets: The target list to be added for scraping
        """
        if labels is None:
            labels = {}
        for target in targets:
            self.add_job(target, labels)

    def find_job_by_target(self, target) -> PrometheusTargetModel:
        """
        Returns the job given a target (ipaddress:port)
        Args:
            target: the target used to find the job IPv4Address:Port

        Returns:
            The Job if it has been found or None
        """
        return next((job for job in self.jobs if target in job.targets), None)

    def find_job_by_labels(self, label) -> PrometheusTargetModel:
        """
        Returns the FIRST job given a label (ipaddress:port)
        Args:
            label: the label used to find the job

        Returns:
            The Job if it has been found or None
        """
        return next((job for job in self.jobs if label in job.labels), None)

    def del_job(self, target: str) -> PrometheusTargetModel:
        """
        Delete (sub) job to be scraped by the server
        Args:
            target: The target to be removed from scraping

        Returns:
            The deleted target
        """
        job_to_del = self.find_job_by_target(target)
        if job_to_del is not None:
            index = self.jobs.index(job_to_del)
            removed = self.jobs.pop(index)
            return removed
        else:
            raise ValueError("Job to be delete has not been found")

    def dump_sd_file(self) -> str:
        """
        Create a local copy (on the host running NFVCL) of the sd_file to be uploaded on the Prometheus server.
        Returns:
            The path of the created file.
        """
        relative_path: str = 'day2_files/prometheus_{}_scraps.yaml'.format(self.id)
        with open(relative_path, 'w') as file:
            file.write(ruamel.yaml.dump(self.dict()['jobs'], Dumper=ruamel.yaml.RoundTripDumper, allow_unicode=True))
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
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the id)
        """
        if isinstance(other, PrometheusServerModel):
            return self.id == other.id
        return False
