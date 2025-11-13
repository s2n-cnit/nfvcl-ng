from verboselogs import VerboseLogger

from nfvcl_common.utils.log import create_logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from nfvcl_rest.models.rest import NFVCLRestError

logger: VerboseLogger = create_logger("NFVCL_REST")

class ExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            logger.exception("Error in REST API", exc_info=e)
            rest_error = NFVCLRestError(error=str(e))
            return Response(rest_error.model_dump_json(), status_code=rest_error.status_code)
