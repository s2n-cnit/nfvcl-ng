import importlib
import inspect
from pathlib import Path
from typing import Any, Optional, Union, List, Text

from ruamel.yaml import YAML, StringIO


def get_class_from_path(class_path: str) -> Any:
    """
    Get class from the give string module path
    Args:
        class_path: module path

    Returns: The class found
    """
    field_type_split = class_path.split(".")

    module_name = ".".join(field_type_split[:-1])
    class_name = field_type_split[-1]

    module = importlib.import_module(module_name)
    found_class = getattr(module, class_name)
    return found_class


def get_class_path_str_from_obj(obj: Any) -> str:
    return f"{obj.__class__.__module__}.{obj.__class__.__qualname__}"


def rel_path(file: str) -> Path:
    """
    Retrieve the abs path of the file from the function in witch this function is called.
    Args:
        file: The file relative location (e.g. 'service/test.yaml')

    Returns:
        the abs path of the file from the function in witch this function is called (e.g. /home/user/service/test.yaml)
    """
    mod_path = Path(inspect.stack()[1].filename).parent
    return Path(mod_path, file)

# define a custom representer for strings
def quoted_presenter(dumper, data):
    if ":"in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
    else:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

class MyYAML(YAML):
    """
    Custom override of the YAML class to allow the dump method to return a string instead of writing to file
    """

    def __init__(self: Any, *, typ: Optional[Union[List[Text], Text]] = None, pure: Any = False, output: Any = None, plug_ins: Any = None) -> None:
        super().__init__(typ=typ, pure=pure, output=output, plug_ins=plug_ins)
        self.preserve_quotes = True
        self.representer.add_representer(str, quoted_presenter)

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


def get_yaml_parser() -> MyYAML:
    return yaml


def get_yaml_parser_jinja2() -> MyYAML:
    return yaml_jinja
