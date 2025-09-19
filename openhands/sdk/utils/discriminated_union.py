import inspect
import json
from abc import ABC
from typing import Annotated, Any, Self, Type, Union

from pydantic import (
    BaseModel,
    Discriminator,
    Tag,
    TypeAdapter,
    computed_field,
    model_validator,
)


_rebuild_required = True


def rebuild_all():
    """Rebuild all polymorphic classes."""
    global _rebuild_required
    _rebuild_required = False
    for cls in _get_all_subclasses(DiscriminatedFieldsMixin):
        cls.model_rebuild(force=True)
    for cls in _get_all_subclasses(DiscriminatedUnionMixin):
        cls.model_rebuild(force=True)


def kind_of(obj) -> str:
    """Get the string value for the kind tag"""
    if isinstance(obj, dict):
        return obj["kind"]
    if not hasattr(obj, "__name__"):
        obj = obj.__class__
    return obj.__name__


def get_known_concrete_subclasses(cls) -> set[Type]:
    """
    Recursively finds and returns all (loaded) subclasses of a given class.
    """
    result = set()
    for subclass in cls.__subclasses__():
        if not _is_abstract(subclass):
            result.add(subclass)
        result.update(get_known_concrete_subclasses(subclass))
    return result


class DiscriminatedFieldsMixin(BaseModel):
    """
    Tags a class where the which may be a discriminated union or contain fields
    which contain a discriminated union. The first time an instance is initialized,
    the schema is loaded, or a model is validated after a subclass is defined we
    regenerate all the polymorphic mappings.
    """

    def __init__(self, *args, **kwargs):
        _rebuild_if_required()
        super().__init__(*args, **kwargs)

    @classmethod
    def model_validate(cls, *args, **kwargs) -> Self:
        _rebuild_if_required()
        return super().model_validate(*args, **kwargs)

    @classmethod
    def model_validate_json(cls, *args, **kwargs) -> Self:
        _rebuild_if_required()
        return super().model_validate_json(*args, **kwargs)

    @classmethod
    def model_json_schema(cls, *args, **kwargs) -> dict[str, Any]:
        _rebuild_if_required()
        return super().model_json_schema(*args, **kwargs)

    def model_dump_json(self, **kwargs):
        # This was overridden because it seems there is a bug where sometimes
        # duplicate fields are produced by model_dump_json which does not appear
        # in model_dump
        return json.dumps(self.model_dump(**kwargs))

    def __init_subclass__(cls, **kwargs):
        """
        When a new subclass is defined, mark that we will need
        to rebuild everything
        """
        global _rebuild_required
        _rebuild_required = True
        return super().__init_subclass__(**kwargs)


class DiscriminatedUnionMixin(DiscriminatedFieldsMixin, ABC):
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
    def resolve_kind(cls, kind: str) -> Type:
        for subclass in get_known_concrete_subclasses(cls):
            if subclass.__name__ == kind:
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
        if _is_abstract(cls) and cls != DiscriminatedUnionMixin:
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
    def get_serializable_type(cls) -> Type:
        """
        Custom method to get the union of all currently loaded
        non absract subclasses
        """

        # If the class is not abstract return self
        if not _is_abstract(cls):
            return cls

        subclasses = get_known_concrete_subclasses(cls)
        if len(subclasses) < 2:
            return cls

        serializable_type = Annotated[
            Union[tuple(Annotated[t, Tag(t.__name__)] for t in subclasses)],
            Discriminator(kind_of),
        ]
        return serializable_type  # type: ignore

    @classmethod
    def model_validate(cls, obj: Any, **kwargs) -> Self:
        if _is_abstract(cls):
            resolved = cls.resolve_kind(kind_of(obj))
        else:
            resolved = super()
        result = resolved.model_validate(obj, **kwargs)
        return result  # type: ignore

    @classmethod
    def model_validate_json(
        cls,
        json_data: str | bytes | bytearray,
        **kwargs,
    ) -> Self:
        data = json.loads(json_data)
        if _is_abstract(cls):
            resolved = cls.resolve_kind(kind_of(data))
        else:
            resolved = super()
        result = resolved.model_validate(data, **kwargs)
        return result  # type: ignore

    @model_validator(mode="before")
    @classmethod
    def _remove_kind(cls, data):
        """After the model has been selected remove the "kind" tag
        so that it doesn't trigger a validation error"""
        if not isinstance(data, dict):
            return
        data = dict(data)
        data.pop("kind", None)
        return data


def _rebuild_if_required():
    if _rebuild_required:
        rebuild_all()


def _is_abstract(type_: Type) -> bool:
    """Determine whether the class directly extends ABC or contains abstract methods"""
    try:
        return inspect.isabstract(type_) or ABC in type_.__bases__
    except Exception:
        return False


def _get_all_subclasses(cls) -> set[Type]:
    """
    Recursively finds and returns all (loaded) subclasses of a given class.
    """
    result = set()
    for subclass in cls.__subclasses__():
        result.add(subclass)
        result.update(_get_all_subclasses(subclass))
    return result
