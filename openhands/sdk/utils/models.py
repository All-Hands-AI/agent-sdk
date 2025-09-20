import inspect
import json
import logging
from abc import ABC
from typing import Annotated, Any, Literal, Self, Type, Union

from pydantic import (
    BaseModel,
    Discriminator,
    Field,
    Tag,
    TypeAdapter,
    model_validator,
)


logger = logging.getLogger(__name__)
_rebuild_required = True


def rebuild_all():
    """Rebuild all polymorphic classes."""
    global _rebuild_required
    _rebuild_required = False
    for cls in _get_all_subclasses(OpenHandsModel):
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


class OpenHandsModel(BaseModel):
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
        kwargs["mode"] = "json"
        return json.dumps(self.model_dump(**kwargs))

    def __init_subclass__(cls, **kwargs):
        """
        When a new subclass is defined, mark that we will need
        to rebuild everything
        """
        global _rebuild_required
        _rebuild_required = True

        return super().__init_subclass__(**kwargs)


class DiscriminatedUnionMixin(OpenHandsModel, ABC):
    """A Base class for members of tagged unions discriminated by the class name.

    This class provides automatic subclass registration and discriminated union
    functionality. Each subclass is automatically registered when defined and
    can be used for polymorphic serialization/deserialization.

    Child classes will automatically have a type field defined, which is used as a
    discriminator for union types.
    """

    kind: str = Field(default="")  # We dynamically update on a per class basis

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
        if cls == DiscriminatedUnionMixin:
            pass
        if _is_abstract(cls):
            subclasses = get_known_concrete_subclasses(cls)
            kinds = [subclass.__name__ for subclass in subclasses]
            if kinds:
                kind = cls.model_fields["kind"]
                kind.annotation = Literal[tuple(kinds)]  # type: ignore
                kind.default = kinds[0]

            # Update kind to be specific - not just str...
            type_adapter = TypeAdapter(cls.get_serializable_type())
            cls.__pydantic_core_schema__ = type_adapter.core_schema
            cls.__pydantic_validator__ = type_adapter.validator
            cls.__pydantic_serializer__ = type_adapter.serializer
            return
        else:
            # Update the kind field to be a literal.
            kind = cls.model_fields["kind"]
            kind.annotation = Literal[cls.__name__]  # type: ignore
            kind.default = cls.__name__

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

        subclasses = list(get_known_concrete_subclasses(cls))
        if not subclasses:
            return cls

        if len(subclasses) == 1:
            # Returning the concrete type ensures Pydantic instantiates the subclass
            # (e.g. Agent) rather than the abstract base (e.g. AgentBase) when there is
            # only ONE concrete subclass.
            return subclasses[0]

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
    def _set_kind(cls, data):
        """For some cases (like models with a default fallback), the incoming
        kind may not match the value so we set it."""
        if not isinstance(data, dict):
            return
        data = dict(data)
        data["kind"] = cls.__name__
        return data

    def __init_subclass__(cls, **kwargs):
        # Check for duplicates
        if DiscriminatedUnionMixin not in cls.__bases__:
            mro = cls.mro()
            union_class = mro[mro.index(DiscriminatedUnionMixin) - 1]
            classes = get_known_concrete_subclasses(union_class)
            kinds = {}
            for subclass in classes:
                kind = kind_of(subclass)
                if kind in kinds:
                    raise ValueError(
                        f"Duplicate kind detected for {union_class} : {cls}, {subclass}"
                    )
                kinds[kind] = subclass

        return super().__init_subclass__(**kwargs)


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


# This is a really ugly hack - (If you are reading this then I am probably more
# upset about it that you are.) - Pydantic type adapters silently take a copy
# of the schema, serializer, and validator from a model, meaning they can
# be created in a state where the models have not yet been updated with
# polymorphic data. I monkey patched a hook in here as unobtrusibley as possible

_orig_type_adapter_init = TypeAdapter.__init__


def _init_with_hook(*args, **kwargs):
    _rebuild_if_required()
    _orig_type_adapter_init(*args, **kwargs)


TypeAdapter.__init__ = _init_with_hook
