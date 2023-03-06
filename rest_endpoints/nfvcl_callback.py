from fastapi import APIRouter
from main import create_logger
from rest_endpoints.rest_callback import CallbackModel

logger = create_logger("Callback Router")

callback_router = APIRouter()


@callback_router.post("{$callback_url}", response_model=CallbackModel)
def post(body: CallbackModel):
    pass
