import textwrap
from enum import Enum
from pathlib import Path
from typing import List, Any, Dict, Optional, Union

from pydantic import Field
from ruamel.yaml.scalarstring import LiteralScalarString

from nfvcl_core.utils.file_utils import render_file_from_template_to_file
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core.utils.blue_utils import get_yaml_parser


def LS(s):
    return LiteralScalarString(textwrap.dedent(s))


class AnsiblePlaybook(NFVCLBaseModel):
    name: Optional[str] = Field(default=None)
    hosts: str = Field()
    connection: Optional[str] = Field(default=None)
    become: bool = Field()
    gather_facts: str = Field()
    tasks: List[Dict[str, Any]] = Field()
    roles: List[str] = Field()
    vars: Dict[str, Any] = Field()


class AnsibleTask(NFVCLBaseModel):
    pass


class AnsibleTaskDescription(NFVCLBaseModel):
    tasks_name: str
    tasks_module: str
    task: AnsibleTask
    register_name: Optional[str] = Field(default=None, description="The name to be given at the variable containing the desired information")

    @classmethod
    def build(cls, tasks_name: str, tasks_module: str, task: AnsibleTask, register_name: str | None = None):
        return AnsibleTaskDescription(tasks_name=tasks_name, tasks_module=tasks_module, task=task, register_name=register_name)


class AnsibleTemplateTask(AnsibleTask):
    src: str = Field()
    dest: str = Field()
    mode: int = Field(default=0o777)
    force: str = Field(default="yes")
    backup: str = Field(default="yes")


class AnsibleCopyTask(AnsibleTask):
    src: str = Field()
    dest: str = Field()
    mode: int = Field(default=0o777)
    force: str = Field(default="yes")
    backup: str = Field(default="yes")
    remote_src: bool = Field(default=False)

class AnsibleCopyContentTask(AnsibleTask):
    content: str = Field()
    dest: str = Field()
    mode: int = Field(default=0o777)
    force: str = Field(default="yes")
    backup: str = Field(default="yes")

class AnsibleReplaceTask(AnsibleTask):
    """
    https://docs.ansible.com/ansible/latest/collections/ansible/builtin/replace_module.html
    """
    path: str = Field()
    regexp: str = Field()
    replace: str = Field()

class AnsibleAptInstallTask(AnsibleTask):
    """
    https://docs.ansible.com/ansible/latest/collections/ansible/builtin/apt_module.html
    """
    name: str = Field()
    state: str = Field()
    update_cache: Optional[str] = Field(default=None)


class AnsibleShellTask(AnsibleTask):
    cmd: str = Field()


class AnsiblePauseTask(AnsibleTask):
    seconds: int = Field()


class ServiceState(Enum):
    STARTED = "started"
    STOPPED = "stopped"
    RESTARTED = "restarted"
    RELOADED = "reloaded"


class AnsibleServiceTask(AnsibleTask):
    name: str
    state: str
    enabled: str = Field(default='true')

class AnsibleBlockInFileTask(AnsibleTask):
    """
    https://docs.ansible.com/ansible/latest/collections/ansible/builtin/blockinfile_module.html
    """
    path: str = Field()
    insertafter: Optional[str] = Field(default=None)
    insertbefore: Optional[str] = Field(default=None)
    block: str = Field()

class AnsiblePlaybookBuilder:
    def __init__(self, name, become=True, gather_facts=False, connection=None):
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
            connection=connection,
            gather_facts="yes" if gather_facts else "no",
            vars={},
            tasks=[],
            roles=[],
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
        if isinstance(value, str):
            value = LS(value)
        self.playbook.vars[key] = value

    def set_vars_from_fields(self, model: NFVCLBaseModel):
        """
        Set Ansible vars from a Pydantic model fields
        Args:
            model: Model to get the fields from
        """

        for field_name in model.model_fields.keys():
            field_value = getattr(model, field_name)
            self.set_var(field_name, field_value)

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
            plays_ = get_yaml_parser().load(stream_)
            for task in plays_[0]["tasks"]:
                self.playbook.tasks.append(task)

    def add_task(self, name: str, task_module: str, task_content: Union[AnsibleTask, Dict], register_output_as: str | None = None, task_vars: Optional[Dict[str, Any]] = None):
        """
        Add a single task to the playbook
        Args:
            name: Name of the task
            task_module: Ansible module of the task
            task_content: Content of the task
            register_output_as: If set the output of the task will be registered to be used by other tasks
            task_vars: Optional vars to pass directly to the task
        """
        dictionary = {
            "name": name,
            task_module: task_content,
        }
        if register_output_as:
            dictionary["register"] = register_output_as
        if task_vars:
            dictionary["vars"] = task_vars
        self.playbook.tasks.append(dictionary)

    def add_role(self, role: str):
        """
        Add a role to the playbook
        Args:
            role: Role to add
        """
        self.playbook.roles.append(role)

    def add_task_embedded(self, task_descr: AnsibleTaskDescription):
        """
        Add a single task to the playbook
        Args:
            task_descr: Ansible task description containing name, module and task to be executed
        """
        self.add_task(task_descr.tasks_name, task_descr.tasks_module, task_descr.task, task_descr.register_name)

    def add_template_task(self, src: Path, dest: str, task_vars: Optional[Dict[str, any]] = None):
        """
        Copy a file to a remote machine resolving the jinja2 templates.
        Add a task of the 'ansible.builtin.template' type, this will copy the file at the src path on the NFVCL server to the dest on the remote machine
        This task will also resolve every jinja2 template in the file using the playbook vars, internal Ansible vars can also be used
        Args:
            src: Path of the source file
            dest: Remote destination
            task_vars: Dict of variables
        """
        self.add_task(
            f"Template task for {dest}",
            "ansible.builtin.template",
            AnsibleTemplateTask(
                src=str(src.absolute()),
                dest=dest,
            ),
            task_vars=task_vars
        )

    def add_render_and_execute_template_task(self, src: Path, task_vars: Optional[Dict[str, any]] = None, rendered_file_prefix: str = ""):
        """
        Render a template ansible file and execute it on the remote machine
        Args:
            src: The source file to be rendered
            task_vars: Variables to be used in the template
            rendered_file_prefix:

        Returns:

        """
        rendered_file = render_file_from_template_to_file(path=src, render_dict=task_vars, prefix_to_name=rendered_file_prefix, extension=".yaml")
        self.add_tasks_from_file(rendered_file)

    def add_copy_task(self, src: str | Path, dest: str, remote_src: bool = False, mode: int = 0o777):
        """
        Add a task of the 'ansible.builtin.copy' type, this will copy the file at the src path to the dest on the remote machine
        Args:
            src: Path of the source file
            dest: Remote destination
            remote_src: True if the source file is on the remote host, False if on the NFVCL machine
            mode: The file permission (default = 0o777)
        """
        self.add_task(
            f"Copy task for {dest}",
            "ansible.builtin.copy",
            AnsibleCopyTask(
                src=str(src.absolute()) if isinstance(src, Path) else src,
                dest=dest,
                remote_src=remote_src,
                mode=mode
            )
        )

    def add_replace_task(self, path: str, regexp: str, replace: str):
        """
        Add a task of the 'ansible.builtin.replace' type, this will replace every occurrence of a regexp in a file with a new string
        Args:
            path: Path of the file
            regexp: Regexp to search in the file
            replace: String used to replace the matches
        """
        self.add_task(
            f"Replace task for {path}",
            "ansible.builtin.replace",
            AnsibleReplaceTask(
                path=path,
                regexp=regexp,
                replace=replace
            )
        )

    def add_apt_install_task(self, package: str, package_version: str = None, update_cache: bool = True):
        """
        Add a task to install a package using apt
        Args:
            package: Name of the package to install
            package_version: Version of the package to install (e.g. for package 'foo=1.00' it will be '1.00')
            update_cache: True if the package cache should be updated before installing the package
        """
        package_full_name = f"{package}={package_version}" if package_version else package
        self.add_task(
            f"Apt install task for package {package}",
            "ansible.builtin.apt",
            AnsibleAptInstallTask(
                name=package_full_name,
                state='present',
                update_cache='yes' if update_cache else 'no'
            )
        )

    def add_apt_uninstall_task(self, package: str):
        """
        Add a task to uninstall a package using apt
        Args:
            package: Name of the package to be uninstalled
        """
        self.add_task(
            f"Apt install task for package {package}",
            "ansible.builtin.apt",
            AnsibleAptInstallTask(
                name=package,
                state='absent'
            )
        )

    def add_gather_template_result_task(self, var_name: str, value_template: str):
        """
        Add a task to gather a variable from the host using Ansible
        Args:
            var_name: Name of the Ansible variable
            value_template: Template that will be executed by Ansible and that will become the value of the variable
        """
        # We need to append the task manually to have variable names in the root structure of the module
        self.playbook.tasks.append({
            "name": f"Gather {var_name} value",
            "ansible.builtin.set_fact": {
                "cacheable": True,
                var_name: value_template
            }
        })

    def add_gather_var_task(self, var_name):
        """
        Simpler version of add_fact_gatherer_task, need only the variable name that will be returned to NFVCL
        Args:
            var_name: Name of the Ansible variable
        """
        self.add_gather_template_result_task(var_name, "{{ " + var_name + " }}")

    def add_shell_task(self, command: str, register_output_as=None):
        """
        Add a shell task to execute commands
        Args:
            command: The command to execute
            register_output_as: The name of the variable in which to register the command output
        """
        self.add_task(
            f"Shell Task '{command}'",
            "ansible.builtin.shell",
            AnsibleShellTask(cmd=LS(command)),
            register_output_as=register_output_as
        )

    def add_service_task(self, service_name: str, service_state: ServiceState, enabled: bool = True):
        """
        Add a service task to start, stop, reload, restart services.
        Args:
            service_name: Name of the service
            service_state: State in which the service will be put
            enabled: True if the service need to start on boot, False otherwise
        """
        self.add_task(
            f"Service Task '{service_name}': state=<{service_state}>, enabled=<{enabled}>",
            "ansible.builtin.service",
            AnsibleServiceTask(name=service_name, state=service_state.value, enabled='true' if enabled else 'false')
        )

    def add_pause_task(self, seconds: int):
        """
        Add a pause task to stop for N seconds
        Args:
            seconds: the number of seconds to stop the playbook
        """
        self.add_task(
            f"Pause Task for '{seconds}' sec",
            "ansible.builtin.pause",
            AnsiblePauseTask(seconds=seconds)
        )

    def add_copy_content_task(self, content: str, dest: str, mode: int = 0o777):
        """
        Add a task of the 'ansible.builtin.copy' type, this will copy the content string in the dest file on the remote machine
        Args:
            content: Content to write in the file
            dest: Remote destination
            mode: The file permission (default = 0o777)
        """
        self.add_task(
            f"Copy content task for {dest}",
            "ansible.builtin.copy",
            AnsibleCopyContentTask(
                content=LS(content),
                dest=dest,
                mode=mode
            )
        )

    def add_blockinfile_task(self, path: str, block: str, insertafter: Optional[str] = None, insertbefore: Optional[str] = None):
        """
        Add a blockinfile task to add a block of text to a file
        Args:
            path: Path of the file
            block: The block of text to insert in the file
            insertafter: If set, the block will be inserted after the line matching this regexp
            insertbefore: If set, the block will be inserted before the line matching this regexp
        """
        self.add_task(
            f"Insert block in file '{path}'",
            "ansible.builtin.blockinfile",
            AnsibleBlockInFileTask(path=path, insertafter=insertafter, insertbefore=insertbefore, block=LS(block))
        )

    def add_set_fact(self, fact_name: str, value: str):
        """
        Set an Ansible fact
        Args:
            fact_name: The name of the fact to set
            value: Value to give to the fact, can be an Ansible template
        """
        self.add_task(
            f"Set {fact_name} fact",
            "set_fact",
            {fact_name: value}
        )

    def add_run_command_and_gather_output_tasks(self, command, output_var_name):
        """
        Add a simple shell task to run a command and gather the stdout to a variable
        Args:
            command: Command to run
            output_var_name: Variable name to store the stdout of the command
        """
        self.add_shell_task(command, register_output_as="tmp_reg")
        self.add_set_fact(output_var_name, "{{ tmp_reg.stdout }}")
        self.add_gather_template_result_task(output_var_name, "{{ tmp_reg.stdout }}")

    def build(self) -> str:
        """
        Build the playbook and return it as a yaml string
        Returns: YAML string of the playbook
        """
        return get_yaml_parser().dump([self.playbook.model_dump(exclude_none=True)])

# if __name__ == "__main__":
#     ansible_builder = AnsiblePlaybookBuilder("Prova")
#     ansible_builder.set_var("test", LS("LINE:\n\tvalue"))
#     print(ansible_builder.build())

# def ansible_run_command(command, output_var_name):
#     builder = AnsiblePlaybookBuilder(f"Running command '{command}'")
#     builder.add_task("Task", "ansible.builtin.shell", AnsibleShellTask(cmd=command), register_output_as="tmp_reg")
#     builder.add_gather_template_result_task(output_var_name, "{{ tmp_reg.stdout }}")
#     return builder.build()
