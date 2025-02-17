from pydantic import BaseModel, ConfigDict


class NFVCLBaseModel(BaseModel):
    # https://docs.pydantic.dev/latest/api/config/
    model_config = ConfigDict(
        populate_by_name=True,  # Allow creating model object using the field name instead of the alias
        extra="forbid",
        use_enum_values=True,  # Needed to be able to save the state to the mongo DB
        validate_default=True,
        validate_assignment=True
    )
