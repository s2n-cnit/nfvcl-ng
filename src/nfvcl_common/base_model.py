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

    def update(self, data: dict) -> NFVCLBaseModel:
        """
        Update the model with the provided data, the data is validated against the model before the update
        This does not return a new model instance, it updates the one on which the method is called.
        Args:
            data: A dictionary with the data to update the model with

        Returns: A reference to the updated model (should be the same as self)
        """
        update = self.model_dump()
        update.update(data)
        for k, v in self.model_validate(update).model_dump(exclude_defaults=True).items():
            setattr(self, k, v)
        return self
