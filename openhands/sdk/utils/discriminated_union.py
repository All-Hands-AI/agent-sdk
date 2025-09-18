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
from pydantic.json_schema import (
    DEFAULT_REF_TEMPLATE,
    GenerateJsonSchema,
    JsonSchemaMode,
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
    def _rebuild_schemas(cls):
        type_adapter = TypeAdapter(cls.get_serializable_type())
        cls.__pydantic_core_schema__ = type_adapter.core_schema
        cls.__pydantic_validator__ = type_adapter.validator
        cls.__pydantic_serializer__ = type_adapter.serializer

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
                superclass._rebuild_schemas()

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

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = "serialization",
    ):
        # By default schemas are generated in "validation" mode - but this
        # will ignore our "kind" attribute and then give an error when
        # deserializing
        return super().model_json_schema(by_alias, ref_template, schema_generator, mode)


def _is_abstract(type_: Type) -> bool:
    """Determine whether the class a is a non abstract subclass of b"""
    try:
        return inspect.isabstract(type_) or ABC in type_.__bases__
    except Exception:
        return False
