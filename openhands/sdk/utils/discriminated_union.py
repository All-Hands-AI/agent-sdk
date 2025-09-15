"""
Utility for creating and managing discriminated unions of Pydantic models.

Pydantic provides native support for discriminated unions via the `Union` type and
the `discriminator` argument to `Field`. However, this requires that all possible
types in the union be known at the time the field is defined. This can be limiting
in scenarios where new types may be defined later.

To address this, we provide a `DiscriminatedUnionMixin` base class that models can
inherit from to automatically register themselves as part of a discriminated union.
We also provide a `DiscriminatedUnionType` type wrapper that can be used in Pydantic
models to indicate that a field should be treated as a discriminated union of all
subclasses of a given base class.

Importantly, this approach allows us to _delay_ the resolution of the union types
until validation time, meaning that new subclasses can be defined and registered
at any time before validation occurs.

Rationale
---------
We keep `kind` as a simple string discriminator for JSON Schema interoperability and
tooling compatibility, but optionally embed a compact, self-describing spec alongside
it for resilience when imports aren't available. This matters for dynamic,
out-of-band producers:

- We need this for MCPAction that are constructed on the fly
  (check openhands/sdk/mcp/tool.py).
- For example, if the MCP was created on the server side, clients may not have access
  to the schema via discriminator mapping at validation time.
- The optional embedded spec lets us reconstruct a temporary Pydantic model and
  validate payloads even when the target subclass can't be imported yet.

Example usage:

    from typing import Annotated
    from pydantic import BaseModel

    from openhands.sdk.utils.discriminated_union import (
        DiscriminatedUnionMixin,
        DiscriminatedUnionType
    )

    # The base class for the union is tagged with DiscriminatedUnionMixin
    class Animal(BaseModel, DiscriminatedUnionMixin):
        name: str

    # We develop a special type to represent the discriminated union of all Animals.
    # This acts just like Animal, but the annotation tells Pydantic to treat it as a
    # discriminated union of all subclasses of Animal (defined so far or in the future).
    AnyAnimal = Annotated[Animal, DiscriminatedUnionType[Animal]]

    class Dog(Animal):
        breed: str

    class Cat(Animal):
        color: str

    class Zoo(BaseModel):
        residents: list[AnyAnimal]

    # Even animals defined after the Zoo class can be included without issue
    class Mouse(Animal):
        size: str

    zoo = Zoo(residents=[
        Dog(name="Fido", breed="Labrador"),
        Cat(name="Whiskers", color="Tabby"),
        Mouse(name="Jerry", size="Small")
    ])

    serialized_zoo = zoo.model_dump_json()
    deserialized_zoo = Zoo.model_validate_json(serialized_zoo)

    assert zoo == deserialized_zoo
"""

from __future__ import annotations

import importlib
from typing import Any, Generic, TypeVar, cast, get_args, get_origin

from pydantic import (
    BaseModel,
    GetJsonSchemaHandler,
    TypeAdapter,
    computed_field,
    create_model,
)
from pydantic_core import core_schema


T = TypeVar("T", bound="DiscriminatedUnionMixin")


def kind_of(t: type) -> str:
    """Get the kind string for a given class."""
    return f"{t.__module__}.{t.__qualname__}"


def resolve_kind(kind: str) -> type[DiscriminatedUnionMixin]:
    """Resolve a kind string back to the corresponding class."""
    t = DiscriminatedUnionMixin.target_subclass(kind)
    if t is None:
        raise ValueError(
            f"Cannot resolve type '{kind}'. "
            "It isn't registered in the DiscriminatedUnion registry. "
            "Make sure the module defining this class was imported/loaded."
        )
    return t


def _resolve_kind_via_import(cls, kind: str):
    parts = kind.split(".")
    for i in range(len(parts) - 1, 0, -1):
        try:
            module = importlib.import_module(".".join(parts[:i]))
        except ModuleNotFoundError:
            continue
        attr = module
        for name in parts[i:]:
            try:
                attr = getattr(attr, name)
            except AttributeError:
                attr = None
                break
        if isinstance(attr, type) and issubclass(attr, cls):
            return attr
    return None


def _type_to_str(tp: Any) -> str:
    """Best-effort readable type name (for fallback only)."""
    try:
        origin = get_origin(tp)
        if origin:
            args = ", ".join(_type_to_str(a) for a in get_args(tp))
            return f"{origin.__name__}[{args}]"
        if isinstance(tp, type):
            return tp.__name__
        return str(tp)
    except Exception:
        return "Any"


class DiscriminatedUnionMixin(BaseModel):
    """A Base class for members of tagged unions discriminated by the class name.

    This class provides automatic subclass registration and discriminated union
    functionality. Each subclass is automatically registered when defined and
    can be used for polymorphic serialization/deserialization.

    Child classes will automatically have a type field defined, which is used as a
    discriminator for union types.
    """

    # Opt-in: include a compact fallback spec next to 'kind'
    # We need this for MCPAction that are constructed on the fly
    # e.g., if the MCP was created on the server side, clients may not
    # have access to schema via discriminator mapping.
    __include_du_spec__: bool = False

    @computed_field  # type: ignore
    @property
    def kind(self) -> str:
        """Property to create kind field from class name when serializing."""
        return kind_of(self.__class__)

    @computed_field  # type: ignore
    @property
    def _du_spec(self) -> dict | None:
        """
        Optional compact spec for resilience:
        {
            "title": "QualifiedName",
            "base": "QualifiedNameOfBaseClass",
            "fields": {
            "name": {"type": "str", "required": True},
            "age":  {"type": "int", "required": False, "default": 0}
            }
        }
        Only emitted if __include_du_spec__ is True.

        We need this for MCPAction that are constructed on the fly
        e.g., if the MCP was created on the server side, clients may not
        have access to schema via discriminator mapping.
        Read openhands/sdk/mcp/tool.py for more context.
        """
        if not getattr(self.__class__, "__include_du_spec__", False):
            return None

        # Determine the DU base class: the class immediately preceding
        # DiscriminatedUnionMixin in the MRO (fallback to self.__class__).
        base_cls = self.__class__
        for c in self.__class__.mro():
            if c is DiscriminatedUnionMixin:
                break
            base_cls = c

        fields: dict[str, dict[str, Any]] = {}
        for fname, f in self.__class__.model_fields.items():
            info: dict[str, Any] = {"type": _type_to_str(f.annotation)}
            if f.is_required():
                info["required"] = True
            else:
                info["required"] = False
                # defaults must be JSON-serializable; skip if they aren’t
                if f.default is not None:
                    try:
                        TypeAdapter(Any).dump_python(f.default)  # smoke test
                        info["default"] = f.default
                    except Exception:
                        pass
            fields[fname] = info

        return {
            "title": kind_of(self.__class__),  # concrete subclass fqname
            "base": kind_of(base_cls),  # DU base fqname
            "fields": fields,
        }

    @classmethod
    def _reconstruct_from_spec(
        cls, spec: dict, payload: dict
    ) -> "DiscriminatedUnionMixin":
        """Build a temporary Pydantic model from a compact field spec.

        Inherits from the base class recorded in spec["base"], if resolvable.
        Note: types are best-effort; unknowns fall back to Any.
        """
        base_cls: type[BaseModel] = cls  # default if we can't import the declared base

        base_name = spec.get("base")
        if isinstance(base_name, str):
            base_cls = _resolve_kind_via_import(cls, base_name) or base_cls

        field_defs: dict[str, tuple[Any, Any]] = {}
        for name, meta in spec.get("fields", {}).items():
            tname = meta.get("type", "Any")
            # Map a few common names; everything else -> Any
            typemap: dict[str, Any] = {
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "Any": Any,
            }
            ann = typemap.get(tname.split("[", 1)[0], Any)
            field_defs[name] = (
                ann,
                ... if meta.get("required", False) else meta.get("default", None),
            )

        Tmp = create_model(
            spec.get("title", "FallbackModel"),
            __base__=base_cls,
            **field_defs,  # type: ignore[arg-type]
        )
        return cast("DiscriminatedUnionMixin", Tmp.model_validate(payload))

    @classmethod
    def target_subclass(cls, kind: str) -> type["DiscriminatedUnionMixin"] | None:
        """Resolve the subclass corresponding to a given kind string.

        Strategy:
        1) First search among already-imported subclasses (fast path)
        2) If not found, attempt to import the module implied by the kind string
           and then search again
        3) As a final attempt, try to retrieve the attribute directly from the
           imported module based on the qualname trail
        """
        # Fast path: search existing subclasses
        worklist = [cls]
        while worklist:
            current = worklist.pop()
            if kind_of(current) == kind:
                return current
            worklist.extend(current.__subclasses__())

        # If not found, attempt to import the module implied by the kind string
        return _resolve_kind_via_import(cls, kind)

    @classmethod
    def model_validate(
        cls: type[T],
        obj: Any,
        *,
        strict=None,
        from_attributes=None,
        context=None,
        **kwargs,
    ) -> T:
        """Custom model validation using registered subclasses for deserialization."""
        # Keep a reference to spec for potential fallback, but never pass it
        # into the target model unless we reconstruct.
        spec = obj.get("_du_spec")
        kind = obj.get("kind")

        # If we can resolve the kind, validate against the target after
        # removing control fields ('kind', '_du_spec').
        if isinstance(kind, str):
            target_class = cls.target_subclass(kind)
            if target_class is not None:
                obj_clean = {
                    k: v for k, v in obj.items() if k not in ("kind", "_du_spec")
                }
                return cast(
                    T,
                    target_class.model_validate(
                        obj_clean,
                        strict=strict,
                        from_attributes=from_attributes,
                        context=context,
                        **kwargs,
                    ),
                )
            # Fallback: if we can't resolve, try reconstructing from spec.
            if isinstance(spec, dict):
                payload = {
                    k: v for k, v in obj.items() if k not in ("kind", "_du_spec")
                }
                return cast(T, cls._reconstruct_from_spec(spec, payload))

        # No usable 'kind': make sure we don't leak '_du_spec' downstream.
        if "_du_spec" in obj:
            obj = {k: v for k, v in obj.items() if k != "_du_spec"}

        return cast(
            T,
            super().model_validate(
                obj,
                strict=strict,
                from_attributes=from_attributes,
                context=context,
                **kwargs,
            ),
        )

    @classmethod
    def model_validate_json(
        cls: type[T],
        json_data: str | bytes | bytearray,
        *,
        strict=None,
        context=None,
        **kwargs,
    ) -> T:
        """Custom JSON validation that uses our custom model_validate method."""
        import json

        # Parse JSON to dict first
        if isinstance(json_data, bytes):
            json_data = json_data.decode("utf-8")

        obj = json.loads(json_data)

        # Use our custom model_validate method
        return cls.model_validate(
            obj,
            strict=strict,
            context=context,
            **kwargs,
        )


class DiscriminatedUnionType(Generic[T]):
    """A type wrapper that enables discriminated union validation for Pydantic fields.

    The wrapped type must be a subclass of `DiscriminatedUnionMixin`.
    """

    def __init__(self, cls: type[T]):
        self.base_class = cls
        self.__origin__ = cls
        self.__args__ = ()

    def __get_pydantic_core_schema__(self, source_type, handler):
        """Define custom Pydantic core schema for this type.

        This schema uses a custom validator function to handle discriminated union
        deserialization based on the 'kind' field.
        """

        # Importantly, this validation function calls the base class model validation
        # _at validation time_, meaning that even if new subclasses are registered after
        # the fact they will still be recognized.
        def validate(v):
            if isinstance(v, self.base_class):
                return v
            if isinstance(v, dict):
                # If we have a 'kind', delegate to the base class DU logic (which
                # may also handle _du_spec fallback if you've added that there).
                if "kind" in v:
                    return self.base_class.model_validate(v)
                # No 'kind': don't leak control fields into strict models
                if "_du_spec" in v:
                    v = {k: val for k, val in v.items() if k != "_du_spec"}
            return self.base_class(**v)

        return core_schema.no_info_plain_validator_function(validate)

    def __get_pydantic_json_schema__(
        self,
        _core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> dict:
        def iter_subclasses(c: type) -> list[type[BaseModel]]:
            seen: set[type] = set()
            stack: list[type] = [c]
            out: list[type[BaseModel]] = []
            while stack:
                cur = stack.pop()
                for sub in cur.__subclasses__():
                    if sub in seen:
                        continue
                    seen.add(sub)
                    if issubclass(sub, BaseModel):
                        out.append(sub)  # type: ignore[arg-type]
                    stack.append(sub)
            return out

        base = self.base_class
        subs: list[type[BaseModel]] = iter_subclasses(base) or [base]

        # Ensure deterministic order for stable schemas across runs
        subs.sort(key=lambda t: kind_of(t))

        one_of: list[dict] = []
        mapping: dict[str, str] = {}

        for sub in subs:
            kind = kind_of(sub)

            # Ask pydantic to generate (and register) the schema for the subclass.
            # Often this returns a $ref into components/schemas.
            sub_schema_json = handler(TypeAdapter(sub).core_schema)

            # Use whatever Pydantic returns directly in the oneOf.
            # If it's a $ref, populate the discriminator mapping
            # with that same ref target.
            one_of.append(sub_schema_json)
            ref_path = (
                sub_schema_json.get("$ref")
                if isinstance(sub_schema_json, dict)
                else None
            )
            if ref_path:
                mapping[kind] = ref_path

        # Plain union with a discriminator. No branch-level wrappers, no consts.
        return {
            "oneOf": one_of,
            "discriminator": (
                {"propertyName": "kind", "mapping": mapping}
                if mapping
                else {"propertyName": "kind"}
            ),
        }

    def __repr__(self):
        return f"DiscriminatedUnion[{self.base_class.__name__}]"

    def __class_getitem__(cls, params):
        """Support type-style subscript syntax like DiscriminatedUnionType[cls]."""
        return cls(params)

    def __instancecheck__(self, instance):
        return isinstance(instance, self.base_class)

    def __subclasscheck__(self, subclass):
        return issubclass(subclass, self.base_class)
