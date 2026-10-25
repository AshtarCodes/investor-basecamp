import json
import os
import subprocess
import sys
from pathlib import Path

from pricing_engine.schema_export import SCHEMA_DIR, render_schemas

COMMITTED = Path(__file__).parent.parent / "schema"


def test_the_committed_schema_is_current():
    expected = render_schemas()
    assert sorted(path.name for path in COMMITTED.glob("*.json")) == sorted(expected)
    for name, text in expected.items():
        assert (COMMITTED / name).read_text() == text, (
            f"{name} is stale: run `pnpm --filter pricing-engine schema`"
        )


def test_export_writes_the_committed_directory_by_default():
    assert SCHEMA_DIR.resolve() == COMMITTED.resolve()


def test_export_is_deterministic_across_processes(tmp_path):
    outputs = []
    for seed in ("0", "1", "12345"):
        target = tmp_path / seed
        subprocess.run(
            [sys.executable, "-m", "pricing_engine.schema_export", str(target)],
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        outputs.append({path.name: path.read_text() for path in sorted(target.glob("*.json"))})
    assert outputs[0] == outputs[1] == outputs[2] == render_schemas()


def test_the_schema_names_provenance_and_the_no_iv_reasons():
    schemas = {name: json.loads(text) for name, text in render_schemas().items()}
    request = schemas["price-request.schema.json"]
    assert "from" in request["$defs"]["Sourced"]["properties"]
    result = json.dumps(schemas["price-result.schema.json"])
    assert "at_or_below_intrinsic" in result and "no_bracket" in result


def test_the_worker_schemas_describe_both_request_types_and_every_response_line():
    schemas = {name: json.loads(text) for name, text in render_schemas().items()}
    request = schemas["worker-request.schema.json"]
    assert request["discriminator"]["propertyName"] == "type"
    assert sorted(request["discriminator"]["mapping"]) == ["batch", "price"]
    response = json.dumps(schemas["worker-response.schema.json"])
    for name in ("Ready", "Success", "Failure", "PricedContract", "FailedContract", "invalid_json"):
        assert name in response
