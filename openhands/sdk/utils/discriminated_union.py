"""Utility for creating and managing discriminated unions of Pydantic models.

Pydantic provides native support for disciriminated unions via the `Union` type and
the `discriminator` argument to `Field`. However, this requires that all possible
types in the union be known at the time the field is defined. This can be limiting
in scenarios where new types may be defined later.

To address this, we provide a `DiscriminatedUnionMixin` base class that models can
inherit from to automatically register themselves as part of a discriminated union.
We also provide a `DiscriminatedUnionType` type wrapper that can be used in Pydantic
models to indicate that a field should be treated as a discriminated union of all
subclasses of a given base class.

Importantly, this approach allows us to _delay_ the resolution of the union types
until validation time, meaning that new subclasses can be defined and registered
at any time before validation occurs.

Example usage:

    from typing import Annotated
    from pydantic import BaseModel

    from openhands.sdk.utils.discriminated_union import (
        DiscriminatedUnionMixin,
        DiscriminatedUnionType
    )

    # The base class for the union is tagged with DiscriminatedUnionMixin
    class Animal(BaseModel, DiscriminatedUnionMixin):
        name: str

    # We develop a special type to represent the discriminated union of all Animals.
    # This acts just like Animal, but the annotation tells Pydantic to treat it as a
    # discriminated union of all subclasses of Animal (defined so far or in the future).
    AnyAnimal = Annotated[Animal, DiscriminatedUnionType[Animal]]

    class Dog(Animal):
        breed: str

    class Cat(Animal):
        color: str

    class Zoo(BaseModel):
        residents: list[AnyAnimal]

    # Even animals defined after the Zoo class can be included without issue
    class Mouse(Animal):
        size: str

    zoo = Zoo(residents=[
        Dog(name="Fido", breed="Labrador"),
        Cat(name="Whiskers", color="Tabby"),
        Mouse(name="Jerry", size="Small")
    ])

    serialized_zoo = zoo.model_dump_json()
    deserialized_zoo = Zoo.model_validate_json(serialized_zoo)

    assert zoo == deserialized_zoo
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel, computed_field
from pydantic_core import core_schema


T = TypeVar("T", bound="DiscriminatedUnionMixin")


class DiscriminatedUnionMixin(BaseModel):
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
        return f"{self.__class__.__module__}.{self.__class__.__qualname__}"

    @classmethod
    def target_subclass(cls, kind: str) -> type[DiscriminatedUnionMixin] | None:
        """Get the subclass corresponding to a given kind name."""
        worklist = [cls]
        while worklist:
            current = worklist.pop()
            if f"{current.__module__}.{current.__qualname__}" == kind:
                return current
            worklist.extend(current.__subclasses__())
        return None

    @classmethod
    def model_validate(
        cls: type[T],
        obj: Any,
        *,
        strict=None,
        from_attributes=None,
        context=None,
        **kwargs,
    ) -> T:
        """Custom model validation using registered subclasses for deserialization."""
        # If we have a 'kind' field but no discriminated union handling,
        # we still need to remove it to avoid extra field errors
        if isinstance(obj, dict) and "kind" in obj:
            kind = obj.get("kind")
            assert isinstance(kind, str)
            obj_without_kind = {k: v for k, v in obj.items() if k != "kind"}
            if (target_class := cls.target_subclass(kind)) is not None:
                return cast(
                    T,
                    target_class.model_validate(
                        obj_without_kind,
                        strict=strict,
                        from_attributes=from_attributes,
                        context=context,
                        **kwargs,
                    ),
                )

        # Fallback to default validation
        return cast(
            T,
            super().model_validate(
                obj,
                strict=strict,
                from_attributes=from_attributes,
                context=context,
                **kwargs,
            ),
        )

    @classmethod
    def model_validate_json(
        cls: type[T],
        json_data: str | bytes | bytearray,
        *,
        strict=None,
        context=None,
        **kwargs,
    ) -> T:
        """Custom JSON validation that uses our custom model_validate method."""
        import json

        # Parse JSON to dict first
        if isinstance(json_data, bytes):
            json_data = json_data.decode("utf-8")

        obj = json.loads(json_data)

        # Use our custom model_validate method
        return cls.model_validate(
            obj,
            strict=strict,
            context=context,
            **kwargs,
        )


class DiscriminatedUnionType(Generic[T]):
    """A type wrapper that enables discriminated union validation for Pydantic fields.

    The wrapped type must be a subclass of `DiscriminatedUnionMixin`.
    """

    def __init__(self, cls: type[T]):
        self.base_class = cls
        self.__origin__ = cls
        self.__args__ = ()

    def __get_pydantic_core_schema__(self, source_type, handler):
        """Define custom Pydantic core schema for this type.

        This schema uses a custom validator function to handle discriminated union
        deserialization based on the 'kind' field.
        """

        # Importantly, this validation function calls the base class model validation
        # _at validation time_, meaning that even if new subclasses are registered after
        # the fact they will still be recognized.
        def validate(v):
            if isinstance(v, self.base_class):
                return v
            if isinstance(v, dict) and "kind" in v:
                return self.base_class.model_validate(v)
            return self.base_class(**v)

        return core_schema.no_info_plain_validator_function(validate)

    def __repr__(self):
        return f"DiscriminatedUnion[{self.base_class.__name__}]"

    def __class_getitem__(cls, params):
        """Support type-style subscript syntax like DiscriminatedUnionType[cls]."""
        return cls(params)

    def __instancecheck__(self, instance):
        return isinstance(instance, self.base_class)

    def __subclasscheck__(self, subclass):
        return issubclass(subclass, self.base_class)
