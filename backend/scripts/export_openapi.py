"""Prints the API's OpenAPI schema as JSON to stdout.

Used by CI to check that the frontend's generated types are up to date:

    uv run python scripts/export_openapi.py > openapi.json

`DATABASE_URL` and a valid `SWISH_NUMBER` must be set, but any values will do:
no connection is made, because the engine is only created in the app's
lifespan.
"""

import json
import sys
from pathlib import Path

# Make `app` importable when the script is run by path from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def main() -> None:
    schema = create_app().openapi()
    sys.stdout.write(json.dumps(schema, indent=2) + '\n')


if __name__ == '__main__':
    main()
