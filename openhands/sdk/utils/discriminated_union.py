from __future__ import annotations

from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel, computed_field
from pydantic_core import core_schema


# Global registry to track subclasses for each DiscriminatedUnionMixin subclass
_DISCRIMINATED_UNION_REGISTRY: dict[
    type[DiscriminatedUnionMixin], dict[str, type[DiscriminatedUnionMixin]]
] = {}

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
        return self.__class__.__name__

    def __init_subclass__(cls, **kwargs):
        """Register subclasses automatically when they are defined."""
        super().__init_subclass__(**kwargs)

        # Find the root DiscriminatedUnionMixin subclass (the direct child of
        # DiscriminatedUnionMixin) to use as the key in the registry.
        root_class = cls
        for base in cls.__mro__[1:]:  # Skip cls itself
            if base is DiscriminatedUnionMixin:
                break
            if (
                issubclass(base, DiscriminatedUnionMixin)
                and base is not DiscriminatedUnionMixin
            ):
                root_class = base

        # Initialize registry for root class if it doesn't exist
        if root_class not in _DISCRIMINATED_UNION_REGISTRY:
            _DISCRIMINATED_UNION_REGISTRY[root_class] = {}

        # Register this class
        _DISCRIMINATED_UNION_REGISTRY[root_class][cls.__name__] = cls

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
        # Only apply custom validation if called on a root class with a registry
        if (
            cls in _DISCRIMINATED_UNION_REGISTRY
            and isinstance(obj, dict)
            and "kind" in obj
        ):
            kind_name = obj["kind"]
            registry = _DISCRIMINATED_UNION_REGISTRY[cls]
            if kind_name in registry:
                target_class = registry[kind_name]
                # Remove the 'kind' field since it's computed
                obj_without_kind = {k: v for k, v in obj.items() if k != "kind"}
                # Call the target class's model_validate directly
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
    """A type wrapper that enables discriminated union validation for Pydantic
    fields.
    """

    def __init__(self, base_class: type[T]):
        self.base_class = base_class
        self.__origin__ = base_class  # For get_origin compatibility
        self.__args__ = ()  # For get_args compatibility

    @property
    def registered_types(self) -> dict[str, type[T]]:
        """Get all currently registered types for this union."""
        return cast(
            dict[str, type[T]],
            _DISCRIMINATED_UNION_REGISTRY.get(self.base_class, {}).copy(),
        )

    @property
    def discriminator_field(self) -> str:
        """The field used for discrimination."""
        return "kind"

    def get_type_for_discriminator(self, kind: str) -> type[T] | None:
        """Get the type associated with a discriminator value."""
        return self.registered_types.get(kind)

    def __get_pydantic_core_schema__(self, source_type, handler):
        """Hook into Pydantic's validation system."""

        def validate(v):
            if isinstance(v, self.base_class):
                return v
            if isinstance(v, dict) and "kind" in v:
                return self.base_class.model_validate(v)
            return self.base_class(**v)

        return core_schema.no_info_plain_validator_function(validate)

    def __repr__(self):
        types = list(self.registered_types.keys())
        if types:
            return f"DiscriminatedUnion[{self.base_class.__name__}: {', '.join(types)}]"
        return f"DiscriminatedUnion[{self.base_class.__name__}]"

    def __class_getitem__(cls, params):
        """Support subscript syntax like DiscriminatedUnion[Animal]."""
        return cls(params)

    def __instancecheck__(self, instance):
        return isinstance(instance, self.base_class)

    def __subclasscheck__(self, subclass):
        return issubclass(subclass, self.base_class)
