import inspect
from abc import ABC
from typing import Annotated, Type, Union

from pydantic import (
    BaseModel,
    Discriminator,
    Tag,
    computed_field,
)


def kind(obj) -> str:
    """Get the tag"""
    if isinstance(obj, dict):
        return obj["kind"]
    if not hasattr(obj, "__name__"):
        obj = obj.__class__
    return obj.__name__


def _is_non_abstract_class(a: type) -> bool:
    """Determine whether the class a is a non abstract subclass of b"""
    try:
        return not inspect.isabstract(a) and ABC not in a.__bases__
    except Exception:
        return False


class DiscriminatedUnionMixin(BaseModel, ABC):
    """A Base class for members of tagged unions discriminated by the class name.

    This class provides automatic subclass registration and discriminated union
    functionality. Each subclass is automatically registered when defined and
    can be used for polymorphic serialization/deserialization.

    Child classes will automatically have a type field defined, which is used as a
    discriminator for union types.
    """

    @computed_field  # type: ignore
    @property
    def kind(self) -> str:
        """Property to create kind field from class name when serializing."""
        return self.__class__.__name__

    @classmethod
    def get_known_concrete_subclasses(cls) -> set[Type]:
        """
        Recursively finds and returns all (loaded) subclasses of a given class.
        """
        result = set()
        for subclass in cls.__subclasses__():
            if _is_non_abstract_class(subclass):
                result.add(subclass)
            result.update(subclass.get_known_concrete_subclasses())
        return result

    @classmethod
    def serializable_type(cls) -> Annotated:
        """Get the serializable type for this discrominated union."""
        subclasses = cls.get_known_concrete_subclasses()
        return Annotated[
            Union[
                tuple(
                    Annotated[subclass, Tag(kind(subclass))] for subclass in subclasses
                )
            ],
            Discriminator(kind),
        ]
