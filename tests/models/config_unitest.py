from __future__ import annotations

from pydantic import BaseModel


class Networks(BaseModel):
    mgmt: str
    data: str


class Vim(BaseModel):
    user: str
    password: str
    url: str


class Config(BaseModel):
    networks: Networks
    vim: Vim


class Model(BaseModel):
    config: Config
