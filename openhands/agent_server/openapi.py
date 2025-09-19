#!/usr/bin/env python3

import json
import os
from pathlib import Path
from typing import Any

from openhands.agent_server.api import api


def fix_openapi_python_client_compatibility(openapi: dict[str, Any]) -> dict[str, Any]:
    """The OpenAPI schema produced by FastAPI is valid, but contains constructs which
    openapi-python-client doesn't support. Manually fix these
    """

    # Definitions for pipeline condenser are the same for input and output. Delete
    # the output, because the API client dislikes having 2 entities with the same title
    del openapi["components"]["schemas"]["PipelineCondenser-Output"]
    as_str = json.dumps(openapi)
    as_str = as_str.replace("PipelineCondenser-Input", "PipelineCondenser")
    as_str = as_str.replace("PipelineCondenser-Output", "PipelineCondenser")
    return json.loads(as_str)


def generate_openapi_schema() -> dict[str, Any]:
    """Generate an OpenAPI schema"""
    openapi = api.openapi()
    openapi = fix_openapi_python_client_compatibility(openapi)
    return openapi


if __name__ == "__main__":
    schema_path = Path(os.environ["SCHEMA_PATH"])
    schema = generate_openapi_schema()
    schema_path.write_text(json.dumps(schema, indent=2))
    print(f"Wrote {schema_path}")
