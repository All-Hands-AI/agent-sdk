from datetime import UTC, datetime


def utc_now():
    """Return the current time in UTC format (Since datetime.utcnow is deprecated)"""
    return datetime.now(UTC)


def patch_fastapi_discriminated_union_support():
    """Patch FastAPI to handle discriminated union schemas without $ref.

    This ensures discriminated unions from DiscriminatedUnionMixin work correctly
    with FastAPI's OpenAPI schema generation. The patch prevents KeyError when
    FastAPI encounters schemas without $ref keys (which discriminated unions use).
    """
    try:
        import fastapi._compat.v2 as fastapi_v2

        _original_remap = fastapi_v2._remap_definitions_and_field_mappings

        def _patched_remap_definitions_and_field_mappings(**kwargs):
            """Patched version that handles schemas w/o $ref (discriminated unions)."""
            field_mapping = kwargs.get("field_mapping", {})
            model_name_map = kwargs.get("model_name_map", {})

            # Build old_name -> new_name map, skipping schemas without $ref
            old_name_to_new_name_map = {}
            for field_key, schema in field_mapping.items():
                model = field_key[0].type_
                if model not in model_name_map:
                    continue
                new_name = model_name_map[model]

                # Skip schemas without $ref (discriminated unions)
                if "$ref" not in schema:
                    continue

                old_name = schema["$ref"].split("/")[-1]
                if old_name in {f"{new_name}-Input", f"{new_name}-Output"}:
                    continue
                old_name_to_new_name_map[old_name] = new_name

            # Replace refs using FastAPI's helper
            from fastapi._compat.v2 import _replace_refs

            new_field_mapping = {}
            for field_key, schema in field_mapping.items():
                new_schema = _replace_refs(
                    schema=schema,
                    old_name_to_new_name_map=old_name_to_new_name_map,
                )
                new_field_mapping[field_key] = new_schema

            definitions = kwargs.get("definitions", {})
            new_definitions = {}
            for key, value in definitions.items():
                new_key = old_name_to_new_name_map.get(key, key)
                new_value = _replace_refs(
                    schema=value,
                    old_name_to_new_name_map=old_name_to_new_name_map,
                )
                new_definitions[new_key] = new_value

            return new_field_mapping, new_definitions

        # Apply the patch
        fastapi_v2._remap_definitions_and_field_mappings = (
            _patched_remap_definitions_and_field_mappings
        )

    except (ImportError, AttributeError):
        # FastAPI not available or internal API changed
        pass
