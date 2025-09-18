import inspect
from abc import ABC
from typing import Annotated, Type, Union

from pydantic import (
    BaseModel,
    Discriminator,
    Tag,
    TypeAdapter,
    computed_field,
)


def kind_of(obj) -> str:
    """Get the tag"""
    if isinstance(obj, dict):
        return obj["kind"]
    if not hasattr(obj, "__name__"):
        obj = obj.__class__
    return obj.__name__


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
            if not _is_abstract(subclass):
                result.add(subclass)
            result.update(subclass.get_known_concrete_subclasses())
        return result

    @classmethod
    def resolve_kind(cls, kind: str) -> Type:
        for subclass in cls.get_known_concrete_subclasses():
            if subclass.kind == kind:
                return subclass
        raise ValueError(f"Unknown kind '{kind}' for {cls}")

    @classmethod
    def model_rebuild(
        cls,
        *,
        force=False,
        raise_errors=True,
        _parent_namespace_depth=2,
        _types_namespace=None,
    ):
        if _is_abstract(cls):
            type_adapter = TypeAdapter(cls.get_serializable_type())
            cls.__pydantic_core_schema__ = type_adapter.core_schema
            cls.__pydantic_validator__ = type_adapter.validator
            cls.__pydantic_serializer__ = type_adapter.serializer
            return

        return super().model_rebuild(
            force=force,
            raise_errors=raise_errors,
            _parent_namespace_depth=_parent_namespace_depth,
            _types_namespace=_types_namespace,
        )

    @classmethod
    def model_validate(
        cls,
        obj,
        *,
        strict=None,
        from_attributes=None,
        context=None,
        by_alias=None,
        by_name=None,
    ):
        if not getattr(cls, "previously_validated", False):
            cls.model_rebuild()
            cls.previously_validated = True
        return super().model_validate(
            obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
            by_alias=by_alias,
            by_name=by_name,
        )

    @classmethod
    def model_validate_json(
        cls, json_data, *, strict=None, context=None, by_alias=None, by_name=None
    ):
        if not getattr(cls, "previously_validated", False):
            cls.model_rebuild()
            cls.previously_validated = True
        return super().model_validate_json(
            json_data,
            strict=strict,
            context=context,
            by_alias=by_alias,
            by_name=by_name,
        )

    @classmethod
    def model_validate_strings(
        cls, obj, *, strict=None, context=None, by_alias=None, by_name=None
    ):
        if not getattr(cls, "previously_validated", False):
            cls.model_rebuild()
            cls.previously_validated = True
        return super().model_validate_strings(
            obj, strict=strict, context=context, by_alias=by_alias, by_name=by_name
        )

    def __init_subclass__(cls, **kwargs):
        """We want to regenerate the schema for any abstract superclass which
        is a DiscriminatedUnion any time a subclass is initialized"""
        super().__init_subclass__(**kwargs)
        if _is_abstract(cls):
            return
        for superclass in cls.mro()[1:]:
            if (
                _is_abstract(superclass)
                and issubclass(superclass, DiscriminatedUnionMixin)
                and not superclass == DiscriminatedUnionMixin
            ):
                superclass.model_rebuild()

    @classmethod
    def get_serializable_type(cls) -> Type:
        """
        Custom method to get the union of all currently loaded
        non absract subclasses
        """

        # If the class is not abstract return self
        if not _is_abstract(cls):
            return cls

        subclasses = cls.get_known_concrete_subclasses()
        if len(subclasses) < 2:
            return cls

        serializable_type = Annotated[
            Union[tuple(Annotated[t, Tag(t.__name__)] for t in subclasses)],
            Discriminator(kind_of),
        ]
        return serializable_type  # type: ignore


def _is_abstract(type_: Type) -> bool:
    """Determine whether the class a is a non abstract subclass of b"""
    try:
        return inspect.isabstract(type_) or ABC in type_.__bases__
    except Exception:
        return False
