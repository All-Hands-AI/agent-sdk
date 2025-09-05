import pytest
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from openhands.sdk.utils.discriminated_union import DiscriminatedUnionMixin


def test_discriminated_union_supports_polymorphic_serialization() -> None:
    """Test that discriminated union supports polymorphic serialization/deserialization.

    That is, we should be able to serialize things in the union and deserialize them
    using the base class.
    """

    class Animal(DiscriminatedUnionMixin):
        name: str

    class Dog(Animal):
        breed: str

    class Cat(Animal):
        color: str

    cat = Cat(name="Whiskers", color="Tabby")
    dog = Dog(name="Fido", breed="Labrador")

    for animal in [cat, dog]:
        serialized_animal = animal.model_dump_json()
        deserialized_animal = Animal.model_validate_json(serialized_animal)
        assert animal == deserialized_animal


def test_discriminated_union_supports_polymorphic_field_serialization() -> None:
    """Test that discriminated union supports polymorphic serialization/deserialization
    when used as a field in another model.
    """

    class Animal(DiscriminatedUnionMixin):
        name: str

    class Dog(Animal):
        breed: str

    class Cat(Animal):
        color: str

    class Carrier(BaseModel):
        animal: Animal

    cat = Cat(name="Whiskers", color="Tabby")
    dog = Dog(name="Fido", breed="Labrador")

    for animal in [cat, dog]:
        carrier = Carrier(animal=animal)
        serialized_carrier = carrier.model_dump_json()
        deserialized_carrier = Carrier.model_validate_json(serialized_carrier)
        assert carrier == deserialized_carrier

    carrier = Carrier(animal=dog)

    serialized_carrier = carrier.model_dump_json()
    deserialized_carrier = Carrier.model_validate_json(serialized_carrier)
    assert carrier == deserialized_carrier


def test_discriminated_union_supports_nested_polymorphic_serialization() -> None:
    """Test that discriminated union supports polymorphic serialization/deserialization
    when nested in a field in another model.
    """

    class Animal(DiscriminatedUnionMixin):
        name: str

    class Dog(Animal):
        breed: str

    class Cat(Animal):
        color: str

    class Zoo(BaseModel):
        residents: list[Animal]

    dog = Dog(name="Fido", breed="Labrador")
    cat = Cat(name="Whiskers", color="Tabby")
    zoo = Zoo(residents=[dog, cat])

    serialized_zoo = zoo.model_dump_json()
    deserialized_zoo = Zoo.model_validate_json(serialized_zoo)
    assert zoo == deserialized_zoo


def test_containers_support_out_of_order_definitions() -> None:
    """Test that discriminated union works even if subclasses are defined after
    containers.
    """

    class Animal(DiscriminatedUnionMixin):
        name: str

    class Dog(Animal):
        breed: str

    class Container(BaseModel):
        animal: Animal

    class Cat(Animal):
        color: str

    dog = Dog(name="Fido", breed="Labrador")
    cat = Cat(name="Whiskers", color="Tabby")

    for animal in [dog, cat]:
        container = Container(animal=animal)
        serialized_container = container.model_dump_json()
        deserialized_container = Container.model_validate_json(serialized_container)
        assert container == deserialized_container


def test_discriminated_union_with_pydantic_validators() -> None:
    """Test that Pydantic validators work correctly with discriminated unions."""

    class Animal(DiscriminatedUnionMixin, BaseModel):
        name: str

        @field_validator("name")
        @classmethod
        def validate_name(cls, v):
            if not v.strip():
                raise ValueError("Name cannot be empty")
            return v.title()

        @model_validator(mode="after")
        def validate_model(self):
            return self

    class Dog(Animal):
        breed: str

        @field_validator("breed")
        @classmethod
        def validate_breed(cls, v):
            return v.title()

    class Cat(Animal):
        color: str

        @field_validator("color")
        @classmethod
        def validate_color(cls, v):
            return v.title()

    # Test direct creation with validators
    dog = Dog(name="fido", breed="labrador")
    assert dog.name == "Fido"
    assert dog.breed == "Labrador"

    # Test model_validate with validators
    dog_data = {"name": "rex", "breed": "german shepherd", "kind": "Dog"}
    dog_from_dict = Animal.model_validate(dog_data)
    assert isinstance(dog_from_dict, Dog)
    assert dog_from_dict.name == "Rex"
    assert dog_from_dict.breed == "German Shepherd"

    # Test model_validate_json with validators
    import json

    dog_json = json.dumps(dog_data)
    dog_from_json = Animal.model_validate_json(dog_json)
    assert isinstance(dog_from_json, Dog)
    assert dog_from_json.name == "Rex"
    assert dog_from_json.breed == "German Shepherd"

    # Test validation errors are properly raised
    with pytest.raises(ValidationError) as exc_info:
        Dog(name="", breed="labrador")
    assert "Name cannot be empty" in str(exc_info.value)


def test_discriminated_union_model_validate_dict() -> None:
    """Test model_validate with dictionary input."""

    class Animal(DiscriminatedUnionMixin, BaseModel):
        name: str

    class Dog(Animal):
        breed: str

    class Cat(Animal):
        color: str

    # Test with valid kind
    dog_data = {"name": "Buddy", "breed": "Golden Retriever", "kind": "Dog"}
    result = Animal.model_validate(dog_data)
    assert isinstance(result, Dog)
    assert result.name == "Buddy"
    assert result.breed == "Golden Retriever"

    cat_data = {"name": "Whiskers", "color": "Orange", "kind": "Cat"}
    result = Animal.model_validate(cat_data)
    assert isinstance(result, Cat)
    assert result.name == "Whiskers"
    assert result.color == "Orange"


def test_discriminated_union_fallback_behavior() -> None:
    """Test fallback behavior when discriminated union logic doesn't apply."""

    class Animal(DiscriminatedUnionMixin, BaseModel):
        name: str

    class Dog(Animal):
        breed: str

    # Test with missing kind - should fallback to base class
    no_kind_data = {"name": "Mystery"}
    result = Animal.model_validate(no_kind_data)
    assert isinstance(result, Animal)
    assert result.name == "Mystery"

    # Test with invalid kind - should fallback to base class
    invalid_kind_data = {"name": "Alien", "kind": "Martian"}
    result = Animal.model_validate(invalid_kind_data)
    assert isinstance(result, Animal)
    assert result.name == "Alien"


def test_discriminated_union_from_attributes() -> None:
    """Test model_validate with from_attributes parameter."""

    class Animal(DiscriminatedUnionMixin, BaseModel):
        name: str

    class Dog(Animal):
        breed: str

    class DogLike:
        def __init__(self):
            self.name = "Buddy"
            self.breed = "Golden Retriever"
            self.kind = "Dog"

    # Currently falls back to base class due to implementation limitation
    # This documents the current behavior
    dog_like = DogLike()
    result = Animal.model_validate(dog_like, from_attributes=True)
    assert isinstance(result, Animal)
    assert result.name == "Buddy"


def test_discriminated_union_preserves_pydantic_parameters() -> None:
    """Test that all Pydantic validation parameters are preserved."""

    class Animal(DiscriminatedUnionMixin, BaseModel):
        name: str

    class Dog(Animal):
        breed: str

    # Test with strict mode
    dog_data = {"name": "Buddy", "breed": "Golden Retriever", "kind": "Dog"}
    result = Animal.model_validate(dog_data, strict=True)
    assert isinstance(result, Dog)

    # Test with context (even though we don't use it here, it should be passed through)
    context = {"test": "value"}
    result = Animal.model_validate(dog_data, context=context)
    assert isinstance(result, Dog)
