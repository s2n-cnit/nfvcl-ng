import importlib

from nfvcl.utils.log import create_logger
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.http_models import BlueprintTypeNotDeclared

logger = create_logger("BlueTypeManager")

class BlueprintModule(NFVCLBaseModel):
    """
    Represents a blueprint module. It is needed to save the info about the module used to process
    requests and responses for a certain path.
    Attributes:
        module (str): The module where the class (of the blueprint module) is found
        class_name (str): The name of the class for the blueprint module
        path(str): The prefix used for requests directed to this blueprint module (e.g '/vyos' for VyOSBlueprint).
    """
    module: str
    class_name: str
    path: str


_path_class_mapping: dict[str, BlueprintModule] = {}


def declare_blue_type(blue_path: str):
    """
    CLASS DECORATOR to be used to declare/register a blueprint class for a certain path.
    Using this decorator, it is possible to declare a blueprint Class to be used when a request on a path arrives.

    {{ base_url }}/nfvcl/v1/api/blue/vyos --path--> /vyos --processed by--> VyOSBlueprintClass

    Args:
        blue_path: The path to be registered for the decorated class (e.g '/vyos' for VyOS).

    Raises:
        ValueError in case of a duplicate path.
    """
    def decorator(original_class):
        if blue_path in _path_class_mapping:
            raise ValueError(f"Duplicate blue type found. {blue_path} is already pointing class {_path_class_mapping[blue_path]}")
        # Saves the mapping path<->class
        _path_class_mapping[blue_path] = BlueprintModule(module=original_class.__module__, class_name=original_class.__qualname__, path=blue_path)
        logger.debug(f"Added route {blue_path} pointing function {original_class.__qualname__}")

        return original_class

    return decorator


def get_blueprint_module(blue_type: str) -> BlueprintModule:
    """
    Return a blueprint Module (module, class, prefix) given the blueprint type.
    This info is used to redirect blueprint creation request to the correct class!
    Args:
        blue_type: The blueprint type.

    Returns:
        The blueprint module containing info about blueprint main class location.
    """
    if blue_type in _path_class_mapping:
        return _path_class_mapping[blue_type]
    else:
        raise BlueprintTypeNotDeclared(blue_type)


def get_blueprint_class(blue_path: str):
    """
    Every blueprint injects the relation type<->Class in the collection.
    This method retrieves the Class, given the blueprint path.
    See declare_blue_type for further information about injection.

    Args:
        blue_path: The path from witch the correct blueprint is taken.

    Returns:
        The class corresponding to the blueprint that should process the request
    """
    blue_path = blue_path.split('/')[-1]
    module = get_blueprint_module(blue_path)
    BlueClass = getattr(importlib.import_module(module.module), module.class_name)
    return BlueClass


def get_registered_modules() -> dict[str, BlueprintModule]:
    """
    Returns a dictionary containing all registered blueprint modules info (path<->class) in the NFVCL.
    Used to load all the blueprint routers in the main blue router
    """
    return _path_class_mapping
