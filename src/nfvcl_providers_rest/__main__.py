import copy
import inspect
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, Dict, Any

import uvicorn
from fastapi import FastAPI, APIRouter, Body, HTTPException
from starlette import status
from starlette.requests import Request
from starlette.responses import Response
from verboselogs import VerboseLogger

from nfvcl_common.utils.log import mod_logger, create_logger, set_log_level  # Order 1
from nfvcl_common.utils.nfvcl_public_utils import NFVCLPublicModel
from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.response_model import OssCompliantResponse, OssStatus
from nfvcl_core_models.task import NFVCLTaskResult
from nfvcl_providers_rest.config import NFVCLProvidersConfigModel, load_nfvcl_providers_config

#### BEFORE IMPORTING ANYTHING FROM NFVCL() main file ####
nfvcl_rest_config: NFVCLProvidersConfigModel

def load_configuration():
    config_path = os.getenv("NFVCL_CONFIG_PATH")
    if config_path:
        if Path(config_path).is_file():
            config = load_nfvcl_providers_config(config_path)
        else:
            logger.error(f"NFVCL_CONFIG_PATH is set to {config_path} but the file does not exist, loading from default location.")
            config = load_nfvcl_providers_config()
    else:
        config = load_nfvcl_providers_config()

    return config

nfvcl_rest_config = load_configuration()
set_log_level(nfvcl_rest_config.log_level)

from nfvcl_providers_rest.nfvcl_providers_main import configure_injection, NFVCLProviders

########### VARS ############
app: FastAPI
logger: VerboseLogger = create_logger("NFVCL_PROVIDERS")


def dummy_callback(result: NFVCLTaskResult):
    """
    Dummy callback function to be used when the callback is not specified. DO NOT REMOVE
    """
    pass


def generate_function_signature(function: Callable, sync=False, override_name=None, override_args=None, override_args_type: Dict[str, Any] = None, override_return_type=None, override_doc=None):
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
    def new_fn(request: Request, response: Response, **kwargs):
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
            response.status_code = status.HTTP_202_ACCEPTED
            # We need to set a dummy callback function for the function to be executed async
            function_return = function(**kwargs, callback=dummy_callback)
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
    # Also handle header parameters
    from fastapi import Header
    for param_name, param in args.items():
        if hasattr(param.annotation, '__metadata__') and len(param.annotation.__metadata__) > 0:
            metadata = param.annotation.__metadata__[0]
            if isinstance(metadata, str):
                if metadata == "application/yaml" or metadata == "text/plain":
                    param.annotation.__metadata__ = (Body(media_type=metadata),)
                elif metadata.startswith("header/"):
                    # For header parameters, replace with FastAPI Header dependency
                    header_name = metadata.split("header/", 1)[1]
                    # Get the base type (e.g., str from Annotated[str, "header/..."])
                    base_type = param.annotation.__origin__ if hasattr(param.annotation, '__origin__') else str
                    # Update the args dict with modified parameter
                    args[param_name] = inspect.Parameter(
                        param_name,
                        param.kind,
                        annotation=base_type,
                        default=Header(..., alias=header_name)
                    )

    # We re-add the original parameters to the new function signature altering the type if needed
    params_original = []
    for param_name, param in args.items():
        # A param with override_args_type None is not added to the signature, useful for day2 without parameters
        if override_args_type and param.name in override_args_type and override_args_type[param_name] is None:
            continue
        params_original.append(inspect.Parameter(
            param_name,
            param.kind,
            annotation=override_args_type[param_name] if override_args_type and param.name in override_args_type else param.annotation,
            default=param.default
        ))

    params.extend(params_original)

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



def readiness():
    """
    Readiness check for the NFVCL
    """
    return Response(status_code=status.HTTP_200_OK)


if __name__ == "__main__":
    start_time = time.perf_counter_ns()

    configure_injection(nfvcl_rest_config)

    nfvcl_provider = NFVCLProviders()
    app = FastAPI(
        title="NFVCL Provider Server",
        description="CNIT/UniGe S2N Lab NFVCL Provider Server",
        # version=global_ref.nfvcl_config.nfvcl.version,
        license_info={
            "name": "Apache 2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        },
        swagger_ui_parameters={"syntaxHighlight.theme": "obsidian", "deepLinking": True},
        lifespan=lifespan,
        ignore_trailing_slash=True,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    # app.add_middleware(ExceptionMiddleware)

    routers_dict: Dict[str, APIRouter] = {}

    for method_callable in nfvcl_provider.get_ordered_public_methods():
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
    for router in routers_dict.values():
        app.include_router(router)

    end_time = time.perf_counter_ns()
    logger.success(f"NFVCL Providers init finished in {str((end_time - start_time) / 1000000000)} sec")
    uvicorn.run(app, host=nfvcl_rest_config.nfvcl_providers.ip, port=nfvcl_rest_config.nfvcl_providers.port)
