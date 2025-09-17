from abc import ABC
from typing import Annotated, Any, Self, Type, Union

from jsonschema import validate
from pydantic import (
    BaseModel,
    Discriminator,
    ModelWrapValidatorHandler,
    Tag,
    computed_field,
    model_validator,
)


def kind(obj) -> str:
    """
    Get the kind of an object.
    If it is an integer, return the value of the "kind" key.
    If it is a class, return its name.
    If it is an instance, get the class and return the name
    """
    if isinstance(obj, dict):
        return obj["kind"]
    if not hasattr(obj, "__name__"):
        obj = obj.__class__
    return obj.__name__


class KindTagMixin(BaseModel, ABC):
    """Mixin which adds a kind property to a class"""

    @computed_field  # type: ignore
    @property
    def kind(self) -> str:
        """ "kind" field for serialization."""
        return self.__class__.__name__


class DynamicModelMixin(ABC):
    """A dynamic model which exposes a model and a schema."""

    model_schema: dict[str, Any]
    model: dict[str, Any]

    @model_validator(mode="wrap")
    @classmethod
    def log_failed_validation(
        cls, data: Any, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        # Make sure the model matches the schema...
        validate(data["model"], data["model_schema"])
        result = handler(data)
        return result


def discriminated_union(*args: Type):
    return Annotated[
        Union[tuple(Annotated[t, Tag(kind(t))] for t in args)], Discriminator(kind)
    ]
