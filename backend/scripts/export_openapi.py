"""Export the FastAPI app's OpenAPI schema to JSON.

`frontend/src/types/schema.ts` is generated from the file this writes
(via `npm run types:generate` in frontend/, using openapi-typescript) —
that's how frontend/src/types/index.ts's type aliases stay honest about
the backend's actual request/response shapes instead of hand-drifting
from them. Doesn't need a running server or a database: `app.openapi()`
builds the schema from the route/Pydantic-model definitions alone.

Usage:
    python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402


def main() -> None:
    output_path = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"
    output_path.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
