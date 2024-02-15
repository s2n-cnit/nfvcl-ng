import abc
from datetime import datetime
from enum import Enum
from typing import Callable, Optional, List

from fastapi import APIRouter

from blueprints_ng.blueprint_ng_provider_interface import BlueprintNGProviderInterface
from models.base_model import NFVCLBaseModel
from pydantic import Field

