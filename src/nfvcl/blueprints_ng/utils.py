import copy
import importlib
import inspect
from pathlib import Path
from types import FunctionType
from typing import Any, Optional, Union, List, Text, Dict

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

def clone_function_and_patch_types(f, func_types: Dict[str, Any], name: str = None, doc: str = None):
    # Create a new function object with the same code, globals, defaults, and closure as f
    new_func = FunctionType(f.__code__, f.__globals__, name or f.__name__, f.__defaults__, f.__closure__)

    # Deep copy the annotations to ensure no shared state
    new_func.__annotations__ = copy.deepcopy(f.__annotations__)

    # Update the type annotations with the provided func_types
    for key, value in func_types.items():
        new_func.__annotations__[key] = value

    # Update the documentation
    new_func.__doc__ = doc

    # Copy other relevant attributes
    new_func.__kwdefaults__ = f.__kwdefaults__

    return new_func

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
