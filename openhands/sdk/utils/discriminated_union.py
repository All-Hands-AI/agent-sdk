from __future__ import annotations

from typing import Any, TypeVar, Union, cast

from pydantic import BaseModel, computed_field


# Global registry to track subclasses for each DiscriminatedUnionMixin subclass
_DISCRIMINATED_UNION_REGISTRY: dict[
    type["DiscriminatedUnionMixin"], dict[str, type["DiscriminatedUnionMixin"]]
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
    def get_discriminated_union(cls):
        """Create a union of all registered subclasses for this DiscriminatedUnionMixin
        hierarchy.
        """
        # Get the registry for this class hierarchy
        registry = _DISCRIMINATED_UNION_REGISTRY.get(cls, {})

        if not registry:
            # If no subclasses registered yet, return just the base class
            return cls

        # Create simple union with all registered subclasses
        union_classes = list(registry.values())
        if cls not in union_classes:
            union_classes.append(cls)  # Add base class as fallback

        return Union[tuple(union_classes)]

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
                # Call the parent's model_validate to avoid recursion
                return cast(
                    T,
                    super(DiscriminatedUnionMixin, target_class).model_validate(
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
