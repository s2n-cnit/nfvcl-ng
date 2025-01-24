from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from nfvcl_rest.models.rest import NFVCLRestError


class ExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            # TODO log exception
            # TODO unify model with the success response one
            rest_error = NFVCLRestError(error=str(e))
            return Response(rest_error.model_dump_json(), status_code=rest_error.status_code)
