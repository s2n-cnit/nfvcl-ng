import copy
import inspect
import logging
import os
import signal
import sys
import typing
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Callable, Dict

import httpx
import uvicorn
from fastapi import APIRouter, FastAPI, Request, Response, Depends, HTTPException, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import Field, BaseModel
from starlette import status
from starlette.responses import RedirectResponse, PlainTextResponse
from starlette.staticfiles import StaticFiles
from verboselogs import VerboseLogger

from nfvcl_core import configure_injection, NFVCL, global_ref
from nfvcl_core.config import NFVCLConfigModel
from nfvcl_core.global_ref import get_nfvcl_config
from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl_core.models.http_models import HttpRequestType
from nfvcl_core.models.response_model import OssCompliantResponse, OssStatus
from nfvcl_core.models.task import NFVCLTaskResult
from nfvcl_core.nfvcl_main import NFVCLPublicModel
from nfvcl_core.utils.file_utils import create_folder
from nfvcl_core.utils.log import mod_logger, create_logger, LOG_FILE_PATH


class RestAnswer202(BaseModel):
    id: str
    operation_type: str = Field(default="", description="The requested operation")
    description: str = 'operation submitted'
    status: str = 'submitted'

class CallbackModel(BaseModel):
    # id: str
    # operation: str
    status: str
    detailed_status: str
    result: str


def call_callback_url(callback_url: str, result: NFVCLTaskResult):
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
    pass
    # print("Dummy callback")
    # print(result)


def generate_function_signature(function: Callable, sync=False, override_name=None, override_args=None, override_args_type: Dict[str, typing.Any] = None, override_return_type=None, override_doc=None):
    # args = {arg: str for arg in re.findall(r'\{(.*?)\}', route_path)}
    args = {param.name: param for param in inspect.signature(function).parameters.values() if param.name != 'callback'}

    if override_args:
        for arg in copy.deepcopy(args):
            if arg in override_args:
                del args[arg]

    def new_fn(request: Request, response: Response, **kwargs):
        if override_args:
            for override_arg in override_args:
                kwargs[override_arg] = override_args[override_arg]

        if sync:
            response.status_code = status.HTTP_200_OK
            return function(**kwargs)
        else:
            callback_function = None
            if "callback" in request.query_params:
                callback_url = request.query_params["callback"]
                callback_function = partial(call_callback_url, callback_url)
            # We need to set a dummy callback function for the function to be executed async

            response.status_code = status.HTTP_202_ACCEPTED
            function_return = function(**kwargs, callback=callback_function if callback_function else dummy_callback)
            if isinstance(function_return, OssCompliantResponse):
                function_return: OssCompliantResponse
                if function_return.status == OssStatus.failed:
                    response.status_code = status.HTTP_400_BAD_REQUEST
            return function_return

    params = []

    # We add the request parameter as the first of the function signature
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


    params_original = [
        inspect.Parameter(
            param_name,
            param.kind,
            annotation=override_args_type[param_name] if override_args_type and param.name in override_args_type else param.annotation,
            default=param.default
        ) for param_name, param in args.items()
    ]

    params.extend(params_original)

    if override_return_type:
        return_type = override_return_type
    else:
        return_type = inspect.signature(function).return_annotation
        if return_type == inspect.Signature.empty:
            return_type = OssCompliantResponse

    new_fn.__signature__ = inspect.Signature(params, return_annotation=return_type)
    new_fn.__annotations__ = {arg: args[arg].annotation for arg in args}
    if override_doc:
        new_fn.__doc__ = override_doc
    else:
        new_fn.__doc__ = function.__doc__
    if override_name:
        new_fn.__name__ = override_name
    else:
        new_fn.__name__ = function.__name__
    return new_fn


class NFVCLRestError(NFVCLBaseModel):
    error: str = Field(default="Internal server error")
    status_code: int = Field(default=500)


async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        # TODO log exception
        # TODO unify model with the success response one
        logger.exception(f"Error: {str(e)}", exc_info=e)
        rest_error = NFVCLRestError(error=str(e))
        return Response(rest_error.model_dump_json(), status_code=rest_error.status_code)


def sort_by_indexes(lst, indexes, reverse=False):
    return [val for (_, val) in sorted(zip(indexes, lst), key=lambda x: x[0], reverse=reverse)]

# TODO example of user authentication
class User(BaseModel):
    username: str
    password: str


users_db = {
    "user1": User(username="user1", password="password1"),
    "user2": User(username="user2", password="password2"),
}

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

from jose import JWTError, jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception


def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if user is None or user.password != form_data.password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


def protected_route(username: str = Depends(get_current_user)):
    return {"message": f"Hello, {username}! This is a protected resource."}

async def close_nfvcl() -> RestAnswer202:
    """
    Terminate the NFVCL.
    """
    os.kill(os.getpid(), signal.SIGTERM)
    return RestAnswer202(id="close", description="Closing")

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


logger: VerboseLogger = create_logger("NFVCL_REST")

PY_MIN_MAJOR = 3
PY_MIN_MINOR = 11

def check_py_version():
    """
    Checks that the python version is equal or grater that the required one
    """
    v_info = sys.version_info
    if v_info.major < PY_MIN_MAJOR or v_info.minor < PY_MIN_MINOR:
        logger.error(f"The version of Python must be greater then {PY_MIN_MAJOR}.{PY_MIN_MINOR}. "
                     f"You are using the {sys.version}")
        exit(-1)


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


# TODO something is broken here
def logs() -> str:
    """
    Return logs from the log file to enable access though the web browser
    """
    nfvcl_config: NFVCLConfigModel = get_nfvcl_config()
    if nfvcl_config.log_level <= 10:  # 20 = INFO, DEBUG = 10
        log_file = Path(LOG_FILE_PATH)
        if log_file.exists() and log_file.is_file():
            return log_file.read_text()
        else:
            return f"File {log_file.absolute()} does not exist"
    else:
        return f"Log level({nfvcl_config.log_level}) is higher than DEBUG(10), HTML logging is disabled."


if __name__ == "__main__":
    check_py_version()

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
        lifespan=lifespan
    )
    app.middleware('http')(catch_exceptions_middleware)

    # TODO: check if working / remove
    accessible_folder = global_ref.nfvcl_config.nfvcl.mounted_folder
    create_folder(accessible_folder)
    app.mount("/files", StaticFiles(directory=accessible_folder, html=True), name="mounted_files")


    app.add_api_route("/logs", logs, methods=["GET"], response_class=PlainTextResponse)


    #Redirect to docs page for APIs
    app.add_api_route("/", lambda: RedirectResponse("/docs"), methods=["GET"], status_code=status.HTTP_308_PERMANENT_REDIRECT, include_in_schema=False)
    app.add_api_route("/close", close_nfvcl, methods=["GET"], status_code=status.HTTP_202_ACCEPTED)



    app.add_api_route("/token", login_for_access_token, methods=["POST"])
    app.add_api_route("/protected", protected_route, methods=["GET"])


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
                    methods=["PUT"], # TODO can a day2 route use a different method?
                    status_code=status.HTTP_202_ACCEPTED
                )

        routers_dict[module.class_name] = module_router

    for router in routers_dict.values():
        app.include_router(router)

    # TODO read host and port from config
    uvicorn.run(app, host="0.0.0.0", port=5002)
