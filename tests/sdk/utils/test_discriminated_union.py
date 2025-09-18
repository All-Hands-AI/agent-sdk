from abc import ABC
from typing import Annotated, Union

from pydantic import (
    Discriminator,
    Tag,
    TypeAdapter,
)

from openhands.sdk.utils.discriminated_union import (
    DiscriminatedUnionMixin,
    kind_of,
)


class Animal(DiscriminatedUnionMixin, ABC):
    name: str


class Cat(Animal):
    pass


class Canine(Animal, ABC):
    pass


class Dog(Canine):
    pass


class Wolf(Canine):
    pass


def test_serializable_type_expected() -> None:
    serializable_type = Animal.get_serializable_type()
    expected_serializable_type = Annotated[
        Union[
            Annotated[Cat, Tag("Cat")],
            Annotated[Dog, Tag("Dog")],
            Annotated[Wolf, Tag("Wolf")],
        ],
        Discriminator(kind_of),
    ]
    assert serializable_type == expected_serializable_type


def test_json_schema() -> None:
    serializable_type = Animal.model_json_schema()
    assert "oneOf" in serializable_type


def test_serialize_single_model() -> None:
    original = Cat(name="Felix")
    dumped = original.model_dump()
    loaded = Animal.model_validate(dumped)
    assert original == loaded
    dumped_json = original.model_dump_json()
    loaded_json = Animal.model_validate_json(dumped_json)
    assert original == loaded_json


def test_serialize_single_model_with_type_adapter() -> None:
    type_adapter = TypeAdapter(Animal)
    original = Cat(name="Felix")
    dumped = type_adapter.dump_python(original)
    loaded = type_adapter.validate_python(dumped)
    assert original == loaded
    dumped_json = type_adapter.dump_json(original)
    loaded_json = type_adapter.validate_json(dumped_json)
    assert original == loaded_json


def test_serialize_model_list() -> None:
    type_adapter = TypeAdapter(list[Animal])
    original = [Cat(name="Felix"), Dog(name="Fido"), Wolf(name="Bitey")]
    dumped = type_adapter.dump_python(original)
    loaded = type_adapter.validate_python(dumped)
    assert original == loaded
