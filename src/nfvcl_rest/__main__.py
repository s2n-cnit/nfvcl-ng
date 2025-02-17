import copy
import inspect
import logging
import os
import signal
import sys
import typing
from contextlib import asynccontextmanager
from functools import partial
from inspect import Parameter
from pathlib import Path
from typing import Callable, Dict

import httpx
import uvicorn
from fastapi import APIRouter, FastAPI, Request, Depends, Body, HTTPException
from file_read_backwards import FileReadBackwards
from starlette import status
from starlette.responses import RedirectResponse, PlainTextResponse, Response, JSONResponse
from starlette.staticfiles import StaticFiles
from verboselogs import VerboseLogger

from nfvcl_core import configure_injection, NFVCL, global_ref
from nfvcl_core.config import NFVCLConfigModel
from nfvcl_core.global_ref import get_nfvcl_config
from nfvcl_core.models.custom_types import NFVCLCoreException
from nfvcl_core.models.http_models import HttpRequestType
from nfvcl_core.models.response_model import OssCompliantResponse, OssStatus
from nfvcl_core.models.task import NFVCLTaskResult
from nfvcl_core.nfvcl_main import NFVCLPublicModel
from nfvcl_core.utils.file_utils import create_folder
from nfvcl_core.utils.log import mod_logger, create_logger, LOG_FILE_PATH
from nfvcl_rest.middleware.authentication_middleware import token, control_token, set_user_manager, logout
from nfvcl_rest.middleware.exception_middleware import ExceptionMiddleware
from nfvcl_rest.models.auth import Oauth2CustomException, Oauth2Errors, OAuth2Response
from nfvcl_rest.models.rest import RestAnswer202, CallbackModel

########### VARS ############
nfvcl: NFVCL
app: FastAPI
logger: VerboseLogger = create_logger("NFVCL_REST")
PY_MIN_MAJOR = 3
PY_MIN_MINOR = 11
DEFAULT_USER = "admin"


########### FUNCTIONS ############

def call_callback_url(callback_url: str, result: NFVCLTaskResult):
    """
    This is the function that will be called by the async function to call the callback url.
    Args:
        callback_url: Callback url to call
        result: Result of the operation to send to the callback
    """
    logger.debug(f"Calling callback url: {callback_url}, msg: {result}")
    try:
        # TODO this is the old callback message, is there a way to improve it?
        callback_model = CallbackModel(
            status="ready" if not result.error else "error",
            detailed_status=str(result.exception) if result.error and result.exception else "Operation completed",
            result=result.result if not result.error and result.result else ""
        )

        httpx.post(callback_url, json=callback_model.model_dump(exclude_none=True))
    except Exception as e:
        logger.error(f"Error calling callback: {str(e)}")


def dummy_callback(result: NFVCLTaskResult):
    """
    Dummy callback function to be used when the callback is not specified. DO NOT REMOVE
    """
    pass


def generate_function_signature(function: Callable, sync=False, override_name=None, override_args=None, override_args_type: Dict[str, typing.Any] = None, override_return_type=None, override_doc=None):
    """
    This function it's used to generate a new function with the correct signature for FastAPI.

    Args:
        function: The original function that will be called by the new function.
        sync: True if the function is sync, False if it is async.
        override_name: Override the name of the function.
        override_args: Override the arguments of the function.
        override_args_type: Override the type of the arguments of the function.
        override_return_type: Override the return type of the function.
        override_doc: Override the docstring of the function.

    Returns: The new function with the correct signature for FastAPI.
    """

    # Take all the argument of the function and remove the callback argument
    args = {param.name: param for param in inspect.signature(function).parameters.values() if param.name != 'callback'}

    # If there are arguments to be overridden, we remove them from the original arguments
    if override_args:
        for arg in copy.deepcopy(args):
            if arg in override_args:
                del args[arg]

    # This is the actual function that will be called by FastAPI
    def new_fn(request: Request, response: Response, logged_user: str = DEFAULT_USER, **kwargs):
        # Override the arguments value if needed
        if override_args:
            for override_arg in override_args:
                kwargs[override_arg] = override_args[override_arg]

        # Check if the function is sync or async
        if sync:
            response.status_code = status.HTTP_200_OK
            try:
                function_result = function(**kwargs)
                return function_result
            except NFVCLCoreException as caught_except:
                raise HTTPException(status_code=caught_except.http_equivalent_code, detail=caught_except.message)
            except Exception as caught_except:
                raise caught_except
        else:
            # If the function is async we need to call it with a callback function
            callback_function = None
            if "callback" in request.query_params:
                callback_url = request.query_params["callback"]
                callback_function = partial(call_callback_url, callback_url)

            response.status_code = status.HTTP_202_ACCEPTED
            # We need to set a dummy callback function for the function to be executed async
            function_return = function(**kwargs, callback=callback_function if callback_function else dummy_callback)
            if isinstance(function_return, OssCompliantResponse):
                function_return: OssCompliantResponse
                if function_return.status == OssStatus.failed:
                    response.status_code = status.HTTP_400_BAD_REQUEST
            return function_return

    # Since we need to manipulate the function signature we need to create a new one
    params = []

    # We add the request parameter as the first of the function signature, this contains information about the REST request
    # it is automatically injected by FastAPI
    params.append(inspect.Parameter(
        "request",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=Request)
    )
    params.append(inspect.Parameter(
        "response",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=Response)
    )

    # If a parameter is of type Annotated[type, "application/yaml"] or other media types it need to be treated as Body by FastAPI
    for param_name, param in args.items():
        if hasattr(param.annotation, '__metadata__') and (param.annotation.__metadata__[0] == "application/yaml" or param.annotation.__metadata__[0] == "text/plain"):
            param.annotation.__metadata__ = (Body(media_type=param.annotation.__metadata__[0]),)

    # We re-add the original parameters to the new function signature altering the type if needed
    params_original = [
        inspect.Parameter(
            param_name,
            param.kind,
            annotation=override_args_type[param_name] if override_args_type and param.name in override_args_type else param.annotation,
            default=param.default
        ) for param_name, param in args.items()
    ]

    params.extend(params_original)

    # If the function requires authentication we add the logged_user parameter
    if get_nfvcl_config().nfvcl.authentication:
        params.append(inspect.Parameter(
            "logged_user",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=str,
            default=Depends(control_token))
        )

    # Override the return type if needed
    if override_return_type:
        return_type = override_return_type
    else:
        return_type = inspect.signature(function).return_annotation
        # If the return type is not specified we set it to OssCompliantResponse
        if return_type == inspect.Signature.empty:
            return_type = OssCompliantResponse

    # Set the new function signature
    new_fn.__signature__ = inspect.Signature(params, return_annotation=return_type)
    new_fn.__annotations__ = {arg: args[arg].annotation for arg in args}

    # Override the docstring and the name of the function if needed
    if override_doc:
        new_fn.__doc__ = override_doc
    else:
        new_fn.__doc__ = function.__doc__
    if override_name:
        new_fn.__name__ = override_name
    else:
        new_fn.__name__ = function.__name__
    return new_fn


def sort_by_indexes(lst, indexes, reverse=False):
    return [val for (_, val) in sorted(zip(indexes, lst), key=lambda x: x[0], reverse=reverse)]


def set_auth_on_api_function(api_function: Callable):
    """
    Set the authentication on the API function if it is required by the configuration.
    Args:
        api_function: The function on which to set the authentication.

    Returns: The function with the authentication set if required.
    """
    sig = inspect.signature(api_function)
    params: Dict[str, Parameter] = dict(sig.parameters)
    if "logged_user" in params and params["logged_user"].annotation == str:
        if get_nfvcl_config().nfvcl.authentication:
            params["logged_user"] = params["logged_user"].replace(default=Depends(control_token))
        else:
            del params["logged_user"]
        api_function.__signature__ = sig.replace(parameters=list(params.values()))
    return api_function


def close_nfvcl(logged_user: str = DEFAULT_USER) -> RestAnswer202:
    """
    Terminate the NFVCL.
    """
    os.kill(os.getpid(), signal.SIGTERM)
    return RestAnswer202(id="close", description="Closing")


def logs(max_lines: int = 500, logged_user: str = DEFAULT_USER) -> str:
    """
    Return logs from the log file to enable access though the web browser
    """
    nfvcl_config: NFVCLConfigModel = get_nfvcl_config()
    if nfvcl_config.log_level <= 10:  # 20 = INFO, DEBUG = 10
        log_file = Path(LOG_FILE_PATH)
        lines = []
        if log_file.exists() and log_file.is_file():
            with FileReadBackwards(log_file.absolute(), encoding="utf-8") as log_file_reader:
                for line in log_file_reader:
                    lines.append(line)
                    if len(lines) >= max_lines:
                        break
                return "\n".join(reversed(lines))
        else:
            return f"File {log_file.absolute()} does not exist"
    else:
        return f"Log level({nfvcl_config.log_level}) is higher than DEBUG(10), HTML logging is disabled."


@asynccontextmanager
async def lifespan(fastapp: FastAPI):
    """
    Mod the unicorn loggers to add colors and custom style
    """
    mod_logger(logging.getLogger('uvicorn'), remove_handlers=True, disable_propagate=True)
    mod_logger(logging.getLogger('uvicorn.access'), remove_handlers=True, disable_propagate=True)
    mod_logger(logging.getLogger('uvicorn.error'), remove_handlers=True, disable_propagate=True)
    mod_logger(logging.getLogger('fastapi'), remove_handlers=True, disable_propagate=True)
    yield
    # If something need to be done after shutdown of the app, it can be done here.


def check_py_version():
    """
    Checks that the python version is equal or grater that the required one
    """
    v_info = sys.version_info
    logger.info(f"Running on Python {v_info.major}.{v_info.minor}")
    if v_info.major < PY_MIN_MAJOR or v_info.minor < PY_MIN_MINOR:
        logger.error(f"The version of Python must be greater then {PY_MIN_MAJOR}.{PY_MIN_MINOR}. "
                     f"You are using the {sys.version}")
        exit(-1)


def readiness():
    """
    Readiness check for the NFVCL
    """
    return Response(status_code=status.HTTP_200_OK)


def setup_main_routes():
    """
    Set up the main routes for the NFVCL
    """
    app.mount("/files", StaticFiles(directory=accessible_folder, html=True), name="mounted_files")
    # Redirect to docs page for APIS
    app.add_api_route("/", lambda: RedirectResponse("/docs"), methods=["GET"], status_code=status.HTTP_308_PERMANENT_REDIRECT, include_in_schema=False)
    # app.add_api_route("/token", login_for_access_token, methods=["POST"])
    app.add_api_route("/token", token, methods=["POST"])
    app.add_api_route("/logout", logout, methods=["POST"])
    ##### PROTECTED MAIN ROUTES #####
    app.add_api_route("/close", set_auth_on_api_function(close_nfvcl), methods=["GET"], status_code=status.HTTP_202_ACCEPTED)
    app.add_api_route("/logs", set_auth_on_api_function(logs), methods=["GET"], response_class=PlainTextResponse)
    app.add_api_route("/ready", readiness, methods=["GET"])


if __name__ == "__main__":
    check_py_version()

    config_path = os.getenv("NFVCL_CONFIG_PATH")
    if config_path:
        if Path(config_path).is_file():
            configure_injection(config_path)
        else:
            logger.error(f"NFVCL_CONFIG_PATH is set to {config_path} but the file does not exist, loading from default location.")
            configure_injection()
    else:
        configure_injection()

    nfvcl = NFVCL()

    app = FastAPI(
        title="NFVCL",
        description="CNIT/UniGe S2N Lab NFVCL",
        version=global_ref.nfvcl_config.nfvcl.version,
        license_info={
            "name": "Apache 2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        },
        swagger_ui_parameters={"syntaxHighlight.theme": "obsidian", "deepLinking": True},
        lifespan=lifespan,
        ignore_trailing_slash=True
    )
    app.add_middleware(ExceptionMiddleware)


    @app.exception_handler(Oauth2CustomException)
    async def oauth2_exception_handler(request: Request, exc: Oauth2CustomException):
        """
        Handle OAuth2 exceptions.
        Args:
            request:
            exc:

        Returns:

        """
        response = JSONResponse(status_code=exc.status_code, content=OAuth2Response(error=Oauth2Errors.INVALID_GRANT, error_description=exc.description).model_dump(exclude_none=True))
        return response


    # TODO: check if working / remove
    accessible_folder = global_ref.nfvcl_config.nfvcl.mounted_folder
    create_folder(accessible_folder)
    set_user_manager(nfvcl.user_manager)

    setup_main_routes()

    routers_dict: Dict[str, APIRouter] = {}

    for method_callable in nfvcl.get_ordered_public_methods():
        if hasattr(method_callable, "nfvcl_public"):
            nfvcl_public: NFVCLPublicModel = method_callable.nfvcl_public
            if nfvcl_public.section.name in routers_dict:
                router = routers_dict[nfvcl_public.section.name]
            else:
                router = APIRouter(
                    prefix=nfvcl_public.section.path,
                    tags=[nfvcl_public.section.name],
                    responses={404: {"description": "Not found"}},
                )
                routers_dict[nfvcl_public.section.name] = router
            router.add_api_route(
                nfvcl_public.path,
                generate_function_signature(method_callable, sync=nfvcl_public.sync),
                methods=[nfvcl_public.method],
                summary=nfvcl_public.summary,
                status_code=status.HTTP_200_OK if nfvcl_public.sync else status.HTTP_202_ACCEPTED,
            )

    for module in nfvcl.get_loaded_blueprints():
        module_router = APIRouter(
            prefix=f"/nfvcl/v2/api/blue/{module.path}",
            tags=[f"Blueprints NG - {module.class_name}"],
            responses={404: {"description": "Not found"}},
        )

        create_type = next(iter(typing.get_type_hints(module.blue_class.create).values()))

        # blue_type: str, blueprint_model: BlueprintNGCreateModel
        module_router.add_api_route(
            "",
            generate_function_signature(
                nfvcl.create_blueprint,
                override_args={"blue_type": module.path},
                override_args_type={"msg": create_type},
                override_doc=module.blue_class.create.__doc__,
                sync=False
            ),
            methods=["POST"],
            status_code=status.HTTP_202_ACCEPTED
        )

        for day2_route in nfvcl.get_module_routes(module.path):
            type_overrides = {}
            if len(typing.get_type_hints(day2_route.function)) > 0:
                type_overrides["msg"] = next(iter(typing.get_type_hints(day2_route.function).values()))
            if HttpRequestType.GET in day2_route.methods:
                module_router.add_api_route(
                    day2_route.final_path,
                    generate_function_signature(
                        nfvcl.get_from_blueprint,
                        override_name=day2_route.function.__name__,
                        override_args={"day2_path": f"{module.path}{day2_route.final_path}"},
                        override_args_type=type_overrides,
                        override_doc=day2_route.function.__doc__,
                        override_return_type=typing.get_type_hints(day2_route.function)["return"],
                        sync=True
                    ),
                    methods=["GET"],
                    status_code=status.HTTP_200_OK
                )
            else:
                module_router.add_api_route(
                    day2_route.final_path,
                    generate_function_signature(
                        nfvcl.update_blueprint,
                        override_name=day2_route.function.__name__,
                        override_args={"day2_path": f"{module.path}{day2_route.final_path}"},
                        override_args_type=type_overrides,
                        override_doc=day2_route.function.__doc__,
                        sync=False
                    ),
                    methods=["PUT"],  # TODO can a day2 route use a different method?
                    status_code=status.HTTP_202_ACCEPTED
                )

        routers_dict[module.class_name] = module_router

    for router in routers_dict.values():
        app.include_router(router)

    config = get_nfvcl_config()
    uvicorn.run(app, host=config.nfvcl.ip, port=config.nfvcl.port)

################### OLD CODE ############################

# def handle_exit(*args):
#     """
#     Handler for exit. Set all managers to be closed, sending them a SIGTERM signal.
#     """
#     # https://stackoverflow.com/a/322317
#     print("Killing all NFVCL processes")
#     os.killpg(0, signal.SIGKILL)
#     # Main process also get killed, no more code can be run
#
#
# if __name__ == '__main__':
#     # https://stackoverflow.com/a/322317
#     os.setpgrp()
#
# # Setup on close handler for the MAIN process.
# # It does NOT work with Pycharm stop button! Only with CTRL+C or SIGTERM or SIGINT!!!!
# # Pycharm terminates the process such that handle_exit is not called.
# atexit.register(handle_exit)
# signal.signal(signal.SIGTERM, handle_exit)
# signal.signal(signal.SIGINT, handle_exit)
