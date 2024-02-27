from pathlib import Path
from typing import List, Any, Dict, Optional, Union, Text

from jinja2 import Environment, FileSystemLoader
from pydantic import Field
from ruamel.yaml import YAML, StringIO
from typing_extensions import deprecated

from models.base_model import NFVCLBaseModel


class MyYAML(YAML):
    """
    Custom override of the YAML class to allow the dump method to return a string instead of writing to file
    """

    def __init__(self: Any, *, typ: Optional[Union[List[Text], Text]] = None, pure: Any = False, output: Any = None, plug_ins: Any = None) -> None:
        super().__init__(typ=typ, pure=pure, output=output, plug_ins=plug_ins)
        self.preserve_quotes = True

    def dump(self, data, stream=None, **kw):
        """
        This override allow to return a string if no stream is provided
        Args:
            data: Data to serialize in yaml
            stream: Output stream for the serialized data
            **kw:

        Returns: YAML string if no stream is provided
        """
        inefficient = False
        if stream is None:
            inefficient = True
            stream = StringIO()
        YAML.dump(self, data, stream, **kw)
        if inefficient:
            return stream.getvalue()


yaml = MyYAML()
yaml_jinja = MyYAML(typ='jinja2')


class AnsiblePlaybook(NFVCLBaseModel):
    name: Optional[str] = Field(default=None)
    hosts: str = Field()
    become: bool = Field()
    gather_facts: str = Field()
    tasks: List[Dict[str, Any]] = Field()
    vars: Dict[str, Any] = Field()


class AnsibleTask(NFVCLBaseModel):
    pass


class AnsibleTemplateTask(AnsibleTask):
    src: str = Field()
    dest: str = Field()
    mode: int = Field(default=664)
    force: str = Field(default="yes")
    backup: str = Field(default="yes")


class AnsiblePlaybookBuilder:
    def __init__(self, name, become=True, gather_facts=False):
        """
        Create a new Ansible Playbook builder
        Args:
            name: Name of the playbook
            become: Escalate privileges, Default to True
            gather_facts: Gather facts, see https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_vars_facts.html require Python on the remote machine
        """
        self.name = name
        self.playbook = AnsiblePlaybook(
            name=self.name,
            hosts="all",
            become=become,
            gather_facts="yes" if gather_facts else "no",
            vars={},
            tasks=[]
        )

    def set_vars(self, vars_: Dict[str, Any]):
        """
        Set the variables for the playbook, this will override existing vars
        Args:
            vars_: Dict of variables
        """
        self.playbook.vars = vars_

    def set_var(self, key: str, value: Any):
        """
        Set a single variable in the playbook
        Args:
            key: Key of the variable
            value: Value of the variable
        """
        self.playbook.vars[key] = value

    def unset_var(self, key: str):
        """
        Delete a variable from the playbook
        Args:
            key: Key of the variable to delete
        Returns:
            True if the variable is present and deleted, False if not present
        """
        if key in self.playbook.vars:
            del self.playbook.vars[key]
            return True
        return False

    def add_tasks_from_file(self, playbook_file: Path):
        """
        Add every task from a playbook file, only add tasks from the first playbook in the file
        Args:
            playbook_file: Path of the playbook file
        """
        with open(playbook_file, 'r+') as stream_:
            plays_ = yaml.load(stream_)
            for task in plays_[0]["tasks"]:
                self.playbook.tasks.append(task)

    @deprecated("This function shouldn't be used, use add_tasks_from_file instead and set the vars in the playbook.")
    def add_tasks_from_file_jinja2(self, playbook_file: Path, confvar):
        env = Environment(loader=FileSystemLoader(playbook_file.parent), extensions=['jinja2_ansible_filters.AnsibleCoreFiltersExtension'])
        template = env.get_template(playbook_file.name)
        plays_ = yaml_jinja.load(template.render(confvar=confvar))
        for task in plays_[0]["tasks"]:
            self.playbook.tasks.append(task)

    def add_task(self, name: str, task_module: str, task_content: AnsibleTask):
        """
        Add a single task to the playbook
        Args:
            name: Name of the task
            task_module: Ansible module of the task
            task_content: Content of the task
        """
        self.playbook.tasks.append({
            "name": name,
            task_module: task_content
        })

    def add_template_task(self, src: Path, dest: str):
        """
        Add a task of the 'ansible.builtin.template' type, this will copy the file at the src path on the NFVCL server to the dest on the remote machine
        This task will also resolve every jinja2 template in the file using the playbook vars, internal Ansible vars can also be used
        Args:
            src: Path of the source file
            dest: Remote destination
        """
        self.add_task(
            f"Template task for {dest}",
            "ansible.builtin.template",
            AnsibleTemplateTask(
                src=str(src.absolute()),
                dest=dest
            )
        )

    def build(self) -> str:
        """
        Build the playbook and return it as a yaml string
        Returns: YAML string of the playbook
        """
        return yaml.dump([self.playbook.model_dump()])
