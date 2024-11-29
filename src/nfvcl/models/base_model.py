from pydantic import BaseModel, ConfigDict


class NFVCLBaseModel(BaseModel):
    # https://docs.pydantic.dev/latest/api/config/
    model_config = ConfigDict(
        populate_by_name=True,  # Allow creating model object using the field name instead of the alias
        extra="forbid"
    )
