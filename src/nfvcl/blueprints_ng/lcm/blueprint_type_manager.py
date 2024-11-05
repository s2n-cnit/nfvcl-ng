import importlib
from inspect import signature
from typing import List, Callable, Any

from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.http_models import BlueprintTypeNotDeclared, HttpRequestType
from nfvcl.utils.log import create_logger

logger = create_logger("BlueTypeManager")


class BlueprintDay2Route(NFVCLBaseModel):
    """
    Represent a route of a blueprint. Every blueprint can have multiple routes.
    This representation is useful to save information

    Attributes:
        blue_type(str): The blueprint type
        final_path (str): The last part of the request path
        methods (List[HttpRequestType]): The allowed HTTP methods (POST, GET, ...)
        function (str): The function that will process the request. It is pointed by (blue_type+final_path)
    """
    blue_type: str
    final_path: str
    methods: List[HttpRequestType]
    function: Callable

    def get_methods_str(self) -> List[str]:
        """
        Returns HTTP methods in string format
        """
        return [item.value for item in self.methods]


class BlueprintModule(NFVCLBaseModel):
    """
    Represents a blueprint module. It is needed to save the info about the module used to process
    requests and responses for a certain path.
    Attributes:
        module (str): The module where the class (of the blueprint module) is found
        class_name (str): The name of the class for the blueprint module
        blue_class (Any): The class for the blueprint module
        path(str): The prefix used for requests directed to this blueprint module (e.g '/vyos' for VyOSBlueprint).
    """
    module: str
    class_name: str
    blue_class: Any
    path: str


class blueprint_type:
    """
    CLASS DECORATOR to be used to declare/register a blueprint class for a certain path.
    Using this decorator, it is possible to declare a blueprint Class to be used when a request on a path arrives.

    {{ base_url }}/nfvcl/v1/api/blue/vyos --path--> /vyos --processed by--> VyOSBlueprintClass

    Args:
        blue_type: The path to be registered for the decorated class (e.g '/vyos' for VyOS).

    Raises:
        ValueError in case of a duplicate path.
    """

    blueprint_module_mapping: dict[str, BlueprintModule] = {}
    path_function_mapping: dict[str, BlueprintDay2Route] = {}

    def __init__(self, blue_type: str):
        self.blue_type = blue_type
        # logger.debug(f"Called __init__ of blueprint_type with type: {self.blue_type}")

    def __call__(self, original_class):
        # logger.debug(f"Called __call__ of blueprint_type with type: {self.blue_type}")

        if self.blue_type in self.blueprint_module_mapping:
            raise ValueError(f"Duplicate blue type found. {self.blue_type} is already pointing class {self.blueprint_module_mapping[self.blue_type]}")
        # Saves the mapping path<->class
        self.blueprint_module_mapping[self.blue_type] = BlueprintModule(module=original_class.__module__, class_name=original_class.__qualname__, path=self.blue_type, blue_class=original_class)
        logger.debug(f"Registered blueprint type {self.blue_type} pointing to class {original_class.__qualname__}")

        # Find and register methods decorated with day2_function
        for method_name in dir(original_class):
            method = getattr(original_class, method_name)
            if hasattr(method, "day2_fun"):
                self.register_day2(method)

        # Don't wrap the class, just return the original
        return original_class

    def register_day2(self, method):
        final_path = method.final_path
        request_type = method.request_type

        if final_path in self.path_function_mapping:
            raise ValueError(f"Duplicate path found. The route {final_path} cannot be added since is already pointing function {method.__qualname__}")

        param_num = len(signature(method).parameters)
        if request_type[0] != HttpRequestType.GET and param_num != 2:
            logger.warning(f"Day2 function must have 2 arguments. {method.__qualname__} has {param_num}")

        # Recreate the complete endpoint path that is given by type + final path. E.g., 'vyos'+'/test_api_path' --> 'vyos/test_api_path'
        endpoint_path = f"{self.blue_type}{final_path}"  # final path contains /
        # Using the endpoint path to map the request path to the correct function to be called
        self.path_function_mapping[endpoint_path] = BlueprintDay2Route(
            blue_type=self.blue_type,
            final_path=final_path,
            methods=request_type,
            function=method
        )
        logger.debug(f"Registered day2 function {endpoint_path} pointing to {method.__qualname__}")

    @classmethod
    def get_blueprint_module(cls, blue_type: str) -> BlueprintModule:
        """
        Return a blueprint Module (module, class, prefix) given the blueprint type.
        This info is used to redirect blueprint creation request to the correct class!
        Args:
            blue_type: The blueprint type.

        Returns:
            The blueprint module containing info about blueprint main class location.
        """
        if blue_type in cls.blueprint_module_mapping:
            return cls.blueprint_module_mapping[blue_type]
        else:
            raise BlueprintTypeNotDeclared(blue_type)

    @classmethod
    def get_blueprint_class(cls, blue_path: str):
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
        module = cls.get_blueprint_module(blue_path)
        BlueClass = getattr(importlib.import_module(module.module), module.class_name)
        return BlueClass

    @classmethod
    def get_registered_modules(cls) -> dict[str, BlueprintModule]:
        """
        Returns a dictionary containing all registered blueprint modules info (path<->class) in the NFVCL.
        Used to load all the blueprint routers in the main blue router
        """
        return cls.blueprint_module_mapping

    @classmethod
    def get_route(cls, path: str) -> BlueprintDay2Route:
        """
        Returns the route corresponding to the path.
        Args:
            path: The path of the request (e.g., vyos/test_api_path)

        Returns:
            The route corresponding to the path
        """
        if path in cls.path_function_mapping:
            return cls.path_function_mapping[path]
        else:
            raise ValueError(f"There is not function for path {path}")

    @classmethod
    def get_module_routes(cls, module_name: str) -> List[BlueprintDay2Route]:
        """
        Returns all the routes that belong to a module.

        Returns:
            All the routes that start with the module name.
        """
        module_routes = []
        for key in cls.path_function_mapping.keys():
            if key.split("/")[0] == module_name:
                module_routes.append(cls.path_function_mapping[key])
        return module_routes

    @classmethod
    def get_routes(cls) -> List[BlueprintDay2Route]:
        """
        Returns all the routes, used to load all the routes in the blueprint.

        Returns:
            All the routes.
        """
        return list(cls.path_function_mapping.values())

    @classmethod
    def get_function_to_be_called(cls, path):
        """
        Returns the function to be called (in the blueprint class), given the path of the request.
        Args:
            path: path of the request

        Returns:
            The name of the function to be called in the blueprint class.
        """
        return cls.get_route(path).function


class day2_function:
    """
    DECORATOR used in bluprint to add routes for day2 operations.
    Maps the path of incoming message to the real function to be called in a blueprint.

    Examples:
        @day2_function("/test_api_path", [HttpRequestType.POST])
        All requests that have the last part of the path corresponding to 'vyos/test_api_path' will be redirected to the decorated function.

    Args:
        final_path: The URL path representing the last part of the URI (e.g. "/test_api_path" -> URL/nfvcl/v2/api/blue/vyos/test_api_path)
        request_type: The type of the request to be accepted on the path (POST, DEL, GET,....)

    Returns:
        The day2 function with added information for mapping
    """

    def __init__(self, final_path, request_type: List[HttpRequestType]):
        self.final_path = final_path
        self.request_type = request_type

    def __call__(self, func):
        func.day2_fun = True
        func.final_path = self.final_path
        func.request_type = self.request_type
        return func
