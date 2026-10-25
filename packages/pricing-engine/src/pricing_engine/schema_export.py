"""Export the request and result JSON Schemas the server generates its TypeScript types from."""

import json
import sys
from pathlib import Path
from typing import Annotated

from pydantic import Field, TypeAdapter

from pricing_engine.models import PriceRequest, PriceResult
from pricing_engine.protocol import Request, Response

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"


def render_schemas() -> dict[str, str]:
    """File name to file text. Keys are sorted and the text is stable run to run."""
    schemas = {
        "price-request.schema.json": PriceRequest.model_json_schema(mode="validation"),
        "price-result.schema.json": PriceResult.model_json_schema(mode="serialization"),
        "worker-request.schema.json": TypeAdapter(
            Annotated[Request, Field(discriminator="type")]
        ).json_schema(mode="validation"),
        "worker-response.schema.json": TypeAdapter(Response).json_schema(mode="serialization"),
    }
    return {
        name: json.dumps(schema, indent=2, sort_keys=True) + "\n"
        for name, schema in schemas.items()
    }


def main() -> None:
    """Write the schemas to the directory in argv[1], or to `schema/` beside `pyproject.toml`."""
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else SCHEMA_DIR
    target.mkdir(parents=True, exist_ok=True)
    for name, text in render_schemas().items():
        (target / name).write_text(text)


if __name__ == "__main__":
    main()
