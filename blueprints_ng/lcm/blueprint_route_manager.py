from inspect import signature
from logging import Logger
from typing import List, Any
from models.base_model import NFVCLBaseModel
from models.http_models import HttpRequestType
from utils.log import create_logger

logger: Logger = create_logger("Blue Route Manager")


class BlueprintDay2Route(NFVCLBaseModel):
    """
    Represent a route of a blueprint. Every blueprint can have multiple routes.
    This representation is useful to save information

    Attributes:
        blue_type(str): The blueprint type
        final_path (str): The last part of the request path
        methods (List[HttpRequestType]): The allowed HTTP methods (POST, GET, ...)
        function (str): The NAME of real function that will process the request. It is pointed by (blue_type+final_path)
        fake_endpoint (Any): The endpoint that redirects to the general function to be called by the day 2 operation. It is needed to make sure that the
        accepted body Model is correct.
    """
    blue_type: str
    final_path: str
    methods: List[HttpRequestType]
    function: str
    fake_endpoint: Any

    def get_methods_str(self) -> List[str]:
        """
        Returns HTTP methods in string format
        """
        return [item.value for item in self.methods]



path_function_mapping: dict[str,BlueprintDay2Route] = {}

def add_route(blue_type: str, final_path: str, request_type: List[HttpRequestType], fake_endpoint: callable):
    """
    DECORATOR used in bluprint to add routes for day2 operations.
    Maps the path of incoming message to the real function to be called in a blueprint.

    Examples:
        VYOS_BLUE_TYPE='vyos'
        @add_route(VYOS_BLUE_TYPE,"/test_api_path", [HttpRequestType.POST], add_area_endpoint)
        All requests that have the last part of the path corresponding to 'vyos/test_api_path' will be redirected to the decorated function.

    Args:
        blue_type: The type of the blueprint. It is used, together with final_path, to determine the function to be called when the request is received.
        final_path: The URL path representing the last part of the URI (e.g. "/test_api_path" -> URL/nfvcl/v2/api/blue/vyos/test_api_path)
        request_type: The type of the request to be accepted on the path (POST, DEL, GET,....)
        fake_endpoint: The endpoint that redirects to the general function to be called by the day 2 operation. It is needed to make sure that the
        accepted body Model is correct. The real function to be called is taken from the decorator.

    Returns:
        The decorated function.
    """

    def decorator(function):
        def wrapper(*args, **kwargs):
            return function(*args, **kwargs)  # Maintains the same function to be called.

        if final_path in path_function_mapping:
            raise ValueError(f"Duplicate path found. The route {final_path} cannot be added since is already pointing function {function.__qualname__}")

        param_num = len(signature(function).parameters)
        if param_num != 2:
            logger.debug(f"Day2 function must have 2 arguments. {function.__qualname__} has {param_num}")

        # Recreate the complete endpoint path that is given by type + final path. E.g., 'vyos'+'/test_api_path' --> 'vyos/test_api_path'
        endpoint_path = f"{blue_type}{final_path}" # final path contains /
        # Using the endpoint path to map the request path to the correct function to be called
        path_function_mapping[endpoint_path] = BlueprintDay2Route(blue_type=blue_type, final_path=final_path, methods=request_type, function=function.__name__, fake_endpoint=fake_endpoint)  # function.__name__ is only the name of the method
        logger.debug(f"Added route {endpoint_path} pointing function {function.__qualname__}")

        return wrapper

    return decorator


def get_route(path: str) -> BlueprintDay2Route:
    """
    Returns the route corresponding to the path.
    Args:
        path: The path of the request (e.g., vyos/test_api_path)

    Returns:
        The route corresponding to the path
    """
    if path in path_function_mapping:
        return path_function_mapping[path]
    else:
        raise ValueError(f"There is not function for path {path}")


def get_module_routes(module_name: str) -> List[BlueprintDay2Route]:
    """
        Returns all the routes that belong to a module.

        Returns:
            All the routes that start with the module name.
        """
    module_routes = []
    for key in path_function_mapping.keys():
        if key.startswith(module_name):
            module_routes.append(path_function_mapping[key])
    return module_routes

def get_routes() -> List[BlueprintDay2Route]:
    """
        Returns all the routes, used to load all the routes in the blueprint.

        Returns:
            All the routes.
        """
    return list(path_function_mapping.values())

def get_function_to_be_called(path):
    """
    Returns the function to be called (in the blueprint class), given the path of the request.
    Args:
        path: path of the request

    Returns:
        The name of the function to be called in the blueprint class.
    """
    return get_route(path).function
