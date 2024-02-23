from inspect import signature
from typing import List, Any
from models.base_model import NFVCLBaseModel
from models.http_models import HttpRequestType


class BlueprintDay2Route(NFVCLBaseModel):
    """
    Represent a route of a blueprint. Every blueprint can have multiple routes.
    This representation is useful to save information

    Attributes:
        path (str):
        methods (List[HttpRequestType]):
        function (str):
        fake_endpoint (Any):
    """
    path: str
    methods: List[HttpRequestType]
    function: str
    fake_endpoint: Any

    def get_methods_str(self) -> List[str]:
        """

        Returns:

        """
        return [item.value for item in self.methods]


"""
    Attributes:
        path_function_mapping:
"""
path_function_mapping: dict[str,BlueprintDay2Route] = {}

def add_route(path: str, request_type: List[HttpRequestType], fake_endpoint: callable):
    """
    DECORATOR used in bluprints to add routes for day2 operations.

    Examples:
        @BlueprintNG.add_route("/test_api_path3234", [HttpRequestType.POST], add_area3234_endpoint)

    Args:
        path: The URL path representing the last part of the URI (e.g. "/test_api_path" -> URL/nfvcl/v2/api/blue/vyos/test_api_path)
        request_type: The type of the request to be accepted on the path
        fake_endpoint: The endpoint that redirects to the real function to be called by the day 2 operation. It is needed to make sure that the
        accepted body type is correct.

    Returns:

    """

    def decorator(function):
        def wrapper(*args, **kwargs):
            return function(*args, **kwargs)

        if path in path_function_mapping:
            raise ValueError(f"Duplicate path found. The route {path} cannot be added since is already pointing function {function.__qualname__}")

        param_num = len(signature(function).parameters)
        if param_num != 2:
            print(f"Day2 function must have 2 arguments. {function.__qualname__} has {param_num}")  # TODO logger.

        path_function_mapping[path] = BlueprintDay2Route(path=path, methods=request_type, function=function.__name__, fake_endpoint=fake_endpoint)  # function.__name__ is only the name of the method
        print(f"Added route {path} pointing function {function.__qualname__}")

        return wrapper

    return decorator


def get_route(path: str) -> BlueprintDay2Route:
    if path in path_function_mapping:
        return path_function_mapping[path]
    else:
        raise ValueError(f"There is not function for path {path}")


def get_routes() -> List[BlueprintDay2Route]:
    return list(path_function_mapping.values())

def get_function_to_be_called(path):
    return get_route(path).function
