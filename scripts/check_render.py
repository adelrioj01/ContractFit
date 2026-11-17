"""Offline verification of the prepared demo deployment (no Render API calls)."""
import argparse
import json
from pathlib import Path

import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--schema", type=Path, help="Validate against a downloaded Render JSON schema")
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[1]
blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8-sig"))
if args.schema:
    from jsonschema import Draft202012Validator

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(blueprint)
    print("Render official JSON schema validation passed.")
service, = blueprint["services"]
database, = blueprint["databases"]
env = {item["key"]: item for item in service["envVars"]}
assert service["runtime"] == "docker"
assert service["autoDeployTrigger"] == "off"
assert service["numInstances"] == 1
assert service["region"] == database["region"]
assert (ROOT / service["dockerfilePath"]).is_file()
assert (ROOT / service["dockerContext"] / "pyproject.toml").is_file()
assert env["DATABASE_URL"]["fromDatabase"] == {
    "name": database["name"], "property": "connectionString"
}
assert env["AUTH_SECRET_KEY"] == {"key": "AUTH_SECRET_KEY", "generateValue": True}
for key, value in {
    "APP_ENV": "production", "STORAGE_BACKEND": "postgres",
    "PROCESSING_MODE": "inline", "SEED_DEMO_DATA": "true",
    "AI_PROVIDER": "offline", "EMBEDDING_PROVIDER": "disabled",
    "SAM_SYNC_ENABLED": "false", "NOTIFICATION_SEND_ENABLED": "false",
}.items():
    assert env[key]["value"] == value, key
upload = Path(env["UPLOAD_DIRECTORY"]["value"])
assert upload.is_relative_to(Path(service["disk"]["mountPath"]))
assert service["disk"]["sizeGB"] == 1
assert database["diskSizeGB"] == 1
assert database["storageAutoscalingEnabled"] is False
assert database["ipAllowList"] == []
assert database["postgresMajorVersion"] == "17"
assert service["plan"] == "0.5c-512mb"
assert database["plan"] == "0.1c-256mb"
assert all("value" not in item or not any(
    secret in item["key"] for secret in ("SECRET", "PASSWORD", "API_KEY")
) for item in service["envVars"])
print("Render demo constraints verified offline.")
