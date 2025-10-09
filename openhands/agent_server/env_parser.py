"""Utility for converting environment variables into pydantic base models.
We couldn't use pydantic-settings for this as we need complex nested types
and polymorphism."""

import inspect
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import UnionType
from typing import Annotated, Literal, Union, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel, SecretStr, TypeAdapter

from openhands.sdk.utils.models import DiscriminatedUnionMixin


# Define Missing type
class MissingType:
    pass


MISSING = MissingType()
JsonType = str | int | float | bool | dict | list | None | MissingType


class EnvParser(ABC):
    """Event parser type"""

    @abstractmethod
    def from_env(self, key: str) -> JsonType:
        """Parse environment variables into a json like structure"""


class BoolEnvParser(EnvParser):
    def from_env(self, key: str) -> bool | MissingType:
        if key not in os.environ:
            return MISSING
        return os.environ[key].upper() in ["1", "TRUE"]  # type: ignore


class IntEnvParser(EnvParser):
    def from_env(self, key: str) -> int | MissingType:
        if key not in os.environ:
            return MISSING
        return int(os.environ[key])


class FloatEnvParser(EnvParser):
    def from_env(self, key: str) -> float | MissingType:
        if key not in os.environ:
            return MISSING
        return float(os.environ[key])


class StrEnvParser(EnvParser):
    def from_env(self, key: str) -> str | MissingType:
        if key not in os.environ:
            return MISSING
        return os.environ[key]


class NoneEnvParser(EnvParser):
    def from_env(self, key: str) -> None | MissingType:
        # Perversely, if the key is present this is not none so we consider it missing
        if key in os.environ:
            return MISSING
        return None


@dataclass
class ModelEnvParser(EnvParser):
    parsers: dict[str, EnvParser]

    def from_env(self, key: str) -> dict | MissingType:
        # First we see is there a base value defined as json...
        value = os.environ.get(key)
        if value:
            result = json.loads(value)
            assert isinstance(result, dict)
        else:
            result = MISSING

        # Check for overrides...
        for field_name, parser in self.parsers.items():
            env_var_name = f"{key}_{field_name.upper()}"

            # First we check that there are possible keys for this field to prevent
            # infinite recursion
            has_possible_keys = next(
                (k for k in os.environ if k.startswith(env_var_name)), False
            )
            if not has_possible_keys:
                continue

            field_value = parser.from_env(env_var_name)
            if field_value is MISSING:
                continue
            if result is MISSING:
                result = {}
            existing_field_value = result.get(field_name, MISSING)  # type: ignore
            new_field_value = merge(existing_field_value, field_value)
            if new_field_value is not MISSING:
                result[field_name] = new_field_value  # type: ignore

        return result


class DictEnvParser(EnvParser):
    def from_env(self, key: str) -> dict | MissingType:
        # Read json from an environment variable
        value = os.environ.get(key)
        if value:
            result = json.loads(value)
            assert isinstance(result, dict)
        else:
            result = MISSING

        return result


@dataclass
class ListEnvParser(EnvParser):
    item_parser: EnvParser

    def from_env(self, key: str) -> list | MissingType:
        if key not in os.environ:
            # Try to read sequentially, starting with 0
            # Return MISSING if there are no items
            result = MISSING
            index = 0
            while True:
                sub_key = f"{key}_{index}"
                item = self.item_parser.from_env(sub_key)
                if item is MISSING:
                    return result
                if result is MISSING:
                    result = []
                result.append(item)  # type: ignore
                index += 1

        # Assume the value is json
        value = os.environ.get(key)
        result = json.loads(value)  # type: ignore
        # A number indicates that the result should be N items long
        if isinstance(result, int):
            result = [MISSING] * result
        else:
            # Otherwise assume the item is a list
            assert isinstance(result, list)

        for index in range(len(result)):
            sub_key = f"{key}_{index}"
            item = self.item_parser.from_env(sub_key)
            item = merge(result[index], item)
            # We permit missing items in the list because these may be filled
            # in later when merged with the output of another parser
            result[index] = item  # type: ignore

        return result


@dataclass
class UnionEnvParser(EnvParser):
    parsers: list[EnvParser]

    def from_env(self, key: str) -> JsonType:
        result = MISSING
        for parser in self.parsers:
            parser_result = parser.from_env(key)
            result = merge(result, parser_result)
        return result


@dataclass
class DelayedParser(EnvParser):
    """Delayed parser for circular dependencies"""

    parser: EnvParser | None = None

    def from_env(self, key: str) -> JsonType:
        assert self.parser is not None
        return self.parser.from_env(key)


def merge(a, b):
    if a is MISSING:
        return b
    if b is MISSING:
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        result = {**a}
        for key, value in b.items():
            result[key] = merge(result.get(key), value)
        return result
    if isinstance(a, list) and isinstance(b, list):
        result = a.copy()
        for index, value in enumerate(b):
            if index >= len(a):
                result[index] = value
            else:
                result[index] = merge(result[index], value)
        return result
    # Favor present values over missing ones
    if b is None:
        return a
    # Later values overwrite earier ones
    return b


def get_env_parser(target_type: type, parsers: dict[type, EnvParser]) -> EnvParser:
    # Check if we have already defined a parser
    if target_type in parsers:
        return parsers[target_type]

    # Check origin
    origin = get_origin(target_type)
    if origin is Annotated:
        # Strip annotations...
        return get_env_parser(get_args(target_type)[0], parsers)
    if origin is UnionType or origin is Union:
        union_parsers = [
            get_env_parser(t, parsers)  # type: ignore
            for t in get_args(target_type)
        ]
        return UnionEnvParser(union_parsers)
    if origin is list:
        parser = get_env_parser(get_args(target_type)[0], parsers)
        return ListEnvParser(parser)
    if origin is dict:
        args = get_args(target_type)
        assert args[0] is str
        assert args[1] in (str, int, float, bool)
        return DictEnvParser()
    if origin is Literal:
        return StrEnvParser()

    if origin and issubclass(origin, BaseModel):
        target_type = origin
    if issubclass(target_type, DiscriminatedUnionMixin) and (
        inspect.isabstract(target_type) or ABC in target_type.__bases__
    ):
        serializable_type = target_type.get_serializable_type()
        if serializable_type != target_type:
            return get_env_parser(target_type.get_serializable_type(), parsers)
    if issubclass(target_type, BaseModel):  # type: ignore
        delayed = DelayedParser()
        parsers[target_type] = delayed  # Prevent circular dependency
        field_parsers = {
            name: get_env_parser(field.annotation, parsers)  # type: ignore
            for name, field in target_type.model_fields.items()
        }
        parser = ModelEnvParser(field_parsers)
        delayed.parser = parser
        parsers[target_type] = parser
        return parser
    raise ValueError(f"unknown_type:{target_type}")


def from_env(
    target_type: type,
    prefix: str = "",
    parsers: dict[type, EnvParser] | None = None,
):
    if parsers is None:
        parsers = {
            str: StrEnvParser(),
            int: IntEnvParser(),
            float: FloatEnvParser(),
            bool: BoolEnvParser(),
            type(None): NoneEnvParser(),
            UUID: StrEnvParser(),
            Path: StrEnvParser(),
            datetime: StrEnvParser(),
            SecretStr: StrEnvParser(),
        }
    parser = get_env_parser(target_type, parsers)
    json_data = parser.from_env(prefix)
    if json_data is MISSING:
        result = target_type()
    else:
        json_str = json.dumps(json_data)
        type_adapter = TypeAdapter(target_type)
        result = type_adapter.validate_json(json_str)
    return result
