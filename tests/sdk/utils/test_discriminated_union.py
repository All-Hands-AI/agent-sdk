from openhands.sdk.utils.discriminated_union import DiscriminatedUnionMixin


def test_discriminated_union_supports_polymorphic_serialization() -> None:
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
