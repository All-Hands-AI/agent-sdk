from typing import Annotated, Union

from pydantic import (
    Discriminator,
    Tag,
    TypeAdapter,
)

from openhands.sdk.utils.discriminated_union import (
    DiscriminatedUnionMixin,
    get_serializable_type,
    kind_of,
)


class Animal(DiscriminatedUnionMixin):
    name: str


class Cat(Animal):
    pass


class Canine(Animal):
    pass


class Dog(Canine):
    pass


class Wolf(Canine):
    pass


def test_serializable_type_expected() -> None:
    serializable_type = get_serializable_type(Animal)
    expected_serializable_type = Annotated[
        Union[
            Annotated[Canine, Tag("Canine")],
            Annotated[Cat, Tag("Cat")],
            Annotated[Dog, Tag("Dog")],
            Annotated[Wolf, Tag("Wolf")],
        ],
        Discriminator(kind_of),
    ]
    assert serializable_type == expected_serializable_type


def test_serialize_single_model() -> None:
    serializable_type = get_serializable_type(Animal)
    type_adapter = TypeAdapter(serializable_type)
    original = Cat(name="Felix")
    dumped = type_adapter.dump_python(original)
    loaded = type_adapter.validate_python(dumped)
    assert original == loaded


def test_serialize_model_list() -> None:
    serializable_type = get_serializable_type(list[Animal])
    type_adapter = TypeAdapter(serializable_type)
    original = [Cat(name="Felix"), Dog(name="Fido"), Wolf(name="Bitey")]
    dumped = type_adapter.dump_python(original)
    loaded = type_adapter.validate_python(dumped)
    assert original == loaded
