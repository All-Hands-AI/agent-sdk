import inspect
from abc import ABC
from datetime import UTC, datetime
from typing import Annotated, Union

from pydantic import Discriminator, Tag


def utc_now():
    """Return the current time in UTC format (Since datetime.utcnow is deprecated)"""
    return datetime.now(UTC)


def is_concrete_subclass(a, b) -> bool:
    try:
        return issubclass(a, b) and not inspect.isabstract(a) and ABC not in a.__bases__
    except Exception:
        return False


def get_all_concrete_subclasses(base_class, cls):
    """
    Recursively finds and returns all (loaded) subclasses of a given class.
    """
    all_subclasses = set()
    for subclass in cls.__subclasses__():
        if is_concrete_subclass(subclass, base_class):
            all_subclasses.add(subclass)
        all_subclasses.update(get_all_concrete_subclasses(base_class, subclass))
    return all_subclasses


def class_discriminator(obj) -> str:
    if not hasattr(obj, "__name__"):
        obj = obj.__class__
    return f"{obj.__module__}.{obj.__name__}"


def get_serializable_polymorphic_type(base_class):
    concrete_subclasses = get_all_concrete_subclasses(base_class, base_class)
    tagged_subclasses = [
        Annotated[cls, Tag(class_discriminator(cls))] for cls in concrete_subclasses
    ]
    result = Annotated[
        Union[tuple(tagged_subclasses)], Discriminator(class_discriminator)
    ]
    return result
