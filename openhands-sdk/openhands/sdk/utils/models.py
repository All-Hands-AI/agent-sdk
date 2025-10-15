import inspect
import json
import logging
from abc import ABC
from typing import Annotated, Any, Literal, Self, Union

from pydantic import (
    BaseModel,
    Discriminator,
    Field,
    Tag,
    TypeAdapter,
)


logger = logging.getLogger(__name__)
_rebuild_required = True
_schema_generation_in_progress = set()  # Track classes currently generating schemas


def _is_abstract(type_: type) -> bool:
    """Determine whether the class directly extends ABC or contains abstract methods"""
    try:
        return inspect.isabstract(type_) or ABC in type_.__bases__
    except Exception:
        return False


def _get_all_subclasses(cls) -> set[type]:
    """
    Recursively finds and returns all (loaded) subclasses of a given class.
    """
    result = set()
    for subclass in cls.__subclasses__():
        result.add(subclass)
        result.update(_get_all_subclasses(subclass))
    return result


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


def get_known_concrete_subclasses(cls) -> list[type]:
    """Recursively returns all concrete subclasses in a stable order,
    without deduping classes that share the same (module, name)."""
    out: list[type] = []
    for sub in cls.__subclasses__():
        # Recurse first so deeper classes appear after their parents
        out.extend(get_known_concrete_subclasses(sub))
        if not _is_abstract(sub):
            out.append(sub)

    # Use qualname to distinguish nested/local classes (like test-local Cat)
    out.sort(key=lambda t: (t.__module__, getattr(t, "__qualname__", t.__name__)))
    return out


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
    def resolve_kind(cls, kind: str) -> type:
        for subclass in get_known_concrete_subclasses(cls):
            if subclass.__name__ == kind:
                return subclass
        raise ValueError(f"Unknown kind '{kind}' for {cls}")

    @classmethod
    def model_json_schema(cls, *args, **kwargs) -> dict[str, Any]:
        """Generate JSON schema, using union schema for abstract classes."""
        _rebuild_if_required()

        # For abstract classes, generate the union schema explicitly
        if _is_abstract(cls):
            union_type = cls.get_serializable_type()
            if union_type is not cls and union_type != cls:
                # Use TypeAdapter to generate schema for the union type
                type_adapter = TypeAdapter(union_type)
                return type_adapter.json_schema(*args, **kwargs)

        # For concrete classes, use default behavior
        return super().model_json_schema(*args, **kwargs)

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
                kind_field = cls.model_fields["kind"]
                kind_field.annotation = Literal[tuple(kinds)]  # type: ignore
                kind_field.default = kinds[0]

            # Create a TypeAdapter for the union type to
            # get its validator and serializer
            type_adapter = TypeAdapter(cls.get_serializable_type())

            # Only set validator and serializer, NOT core_schema
            # This allows __get_pydantic_core_schema__ to generate proper schemas
            # for FastAPI's OpenAPI generation while still using the union logic
            # for runtime validation
            cls.__pydantic_validator__ = type_adapter.validator
            cls.__pydantic_serializer__ = type_adapter.serializer

            # Don't set __pydantic_core_schema__ to avoid
            # breaking FastAPI's JSON schema generation
            # The schema will be generated by __get_pydantic_core_schema__ which returns
            # a model schema that FastAPI can handle properly
            return

        return super().model_rebuild(
            force=force,
            raise_errors=raise_errors,
            _parent_namespace_depth=_parent_namespace_depth,
            _types_namespace=_types_namespace,
        )

    @classmethod
    def get_serializable_type(cls) -> type:
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
            Union[*tuple(Annotated[t, Tag(t.__name__)] for t in subclasses)],
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

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # If concrete, stamp kind Literal and collision check
        if not _is_abstract(cls):
            # 1) Stamp discriminator
            cls.kind = cls.__name__
            cls.__annotations__["kind"] = Literal[cls.__name__]

            # 2) Collision check
            mro = cls.mro()
            union_class = mro[mro.index(DiscriminatedUnionMixin) - 1]
            concretes = get_known_concrete_subclasses(union_class)  # sorted list
            kinds: dict[str, type] = {}
            for sub in concretes:
                k = kind_of(sub)
                if k in kinds and kinds[k] is not sub:
                    raise ValueError(
                        f"Duplicate kind detected for {union_class} : {cls}, {sub}"
                    )
                kinds[k] = sub

        # Rebuild any abstract union owners in the MRO that rely on subclass sets
        for base in cls.mro():
            # Stop when we pass ourselves
            if base is cls:
                continue
            # Only rebuild abstract DiscriminatedUnion owners
            if (
                isinstance(base, type)
                and issubclass(base, DiscriminatedUnionMixin)
                and _is_abstract(base)
            ):
                base.model_rebuild(force=True)


def _rebuild_if_required():
    if _rebuild_required:
        rebuild_all()
