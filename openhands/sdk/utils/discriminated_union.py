import inspect
from abc import ABC
from copy import deepcopy
from typing import Annotated, Type, Union, get_args, get_origin

from pydantic import (
    BaseModel,
    Discriminator,
    Tag,
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


def _is_subclass(a: Type, b: Type):
    try:
        return issubclass(a, b)
    except Exception:
        return False


def _is_abstract(type_: Type) -> bool:
    """Determine whether the class a is a non abstract subclass of b"""
    try:
        return inspect.isabstract(type_) or ABC in type_.__bases__
    except Exception:
        return False


def get_serializable_type(type_: Type) -> Type:
    if _is_subclass(type_, DiscriminatedUnionMixin):
        # Build a structure for all concrete subtypes and all fields
        concrete_subclasses = [
            _get_serializable_undescriminated_type(cls)
            for cls in type_.get_known_concrete_subclasses()
        ]

        if not concrete_subclasses and _is_abstract(type_):
            raise ValueError(f"No subclasses found for {type_}")

        if concrete_subclasses:
            tagged_subclasses = tuple(
                Annotated[cls, Tag(cls.__name__)] for cls in concrete_subclasses
            )

            result = Annotated[Union[tagged_subclasses], Discriminator(kind_of)]
            return result  # type: ignore

    return _get_serializable_undescriminated_type(type_)


def _get_serializable_undescriminated_type(type_: Type) -> Type:
    if _is_subclass(type_, BaseModel):
        # Build a set of updated fields
        updated_fields = {}
        for field_name, field_info in type_.model_fields.items():
            field_serializable_type = get_serializable_type(field_info.annotation)
            if field_serializable_type == field_info.annotation:
                continue
            updated_field = deepcopy(field_info)
            updated_field.annotation = field_serializable_type
            updated_fields[field_name] = updated_field

        # If there were no updated fields return the original class
        if not updated_fields:
            return type_

        # Define and return a new class using the updated fields
        # (Which extends the original)
        updated_annotations = {f.name: f.type for f in updated_fields.items()}  # type: ignore
        updated_fields["__annotations__"] = updated_annotations
        updated_class = type(type_.__name__, (type_,), updated_fields)
        return updated_class

    # If the type has generics, process each of these in turn...
    origin = get_origin(type_)
    if origin:
        args = get_args(type_)
        updated_origin = get_serializable_type(origin)
        updated_args = tuple(get_serializable_type(arg) for arg in args)
        updated_type = updated_origin[updated_args]  # type: ignore
        return updated_type

    return type_
