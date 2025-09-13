import json
from pathlib import Path

from openhands.server.main import app


def main() -> None:
    schema = app.openapi()
    out = Path("openhands/server/openapi.json")
    out.write_text(json.dumps(schema, indent=2))
    print(f"Wrote {out.resolve()}")


if __name__ == "__main__":
    main()
