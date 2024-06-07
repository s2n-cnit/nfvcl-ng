from __future__ import annotations

from enum import Enum

from fastapi import HTTPException, status, Header



############### EXCEPTIONS ###############################
class BlueprintNotFoundException(HTTPException):
    def __init__(self, blueprint_id: str) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"Blueprint {blueprint_id} not found", headers=None)


class BlueprintAlreadyExisting(HTTPException):
    def __init__(self, blueprint_id: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=f"Blueprint {blueprint_id} already existing", headers=None)


class BlueprintTypeNotDeclared(HTTPException):
    def __init__(self, blue_type: str) -> None:
        super().__init__(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=f"Blueprint type >{blue_type}< has not been implemented", headers=None)


class HttpRequestType(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
