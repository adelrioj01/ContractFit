"""Build and probe disposable Docker resources; no Render calls or local .env loading."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

CONTENT = b"Title: Synthetic HVAC Smoke\nScope: HVAC maintenance\nResponse deadline: 2099-12-31"


def inside(mode: str) -> None:
    base = "http://127.0.0.1:10000"

    def request(path: str, data: bytes | None = None, token: str = "",
                content_type: str = "application/json") -> object:
        headers = {"Content-Type": content_type}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with urlopen(Request(base + path, data=data, headers=headers), timeout=15) as response:
            body = response.read()
            return json.loads(body) if "json" in response.headers.get("Content-Type", "") else body

    deadline = time.monotonic() + 90
    while True:
        try:
            assert request("/health") == {"status": "ok", "environment": "production"}
            break
        except (URLError, TimeoutError):
            if time.monotonic() > deadline:
                raise RuntimeError("Container failed readiness on configured PORT") from None
            time.sleep(1)
    assert b"ContractFit" in request("/")
    login = urlencode({"username": "demo@contractfit.local", "password": "contractfit-demo-password"})
    token = request("/api/auth/token", login.encode(), content_type="application/x-www-form-urlencoded")["access_token"]
    catalog = request("/api/opportunities", token=token)
    assert catalog
    if mode == "before":
        boundary = "contractfit-smoke-boundary"
        data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                'filename="render-smoke.txt"\r\nContent-Type: text/plain\r\n\r\n').encode()
        data += CONTENT + f"\r\n--{boundary}--\r\n".encode()
        uploaded = request("/api/documents/upload", data, token, f"multipart/form-data; boundary={boundary}")
        assert uploaded["job"]["status"] == "completed"
        assert uploaded["document"]["status"] == "ready"
        assert uploaded["opportunity"] is not None
        other = request("/api/auth/register", json.dumps({
            "organization_name": "Synthetic other tenant", "email": "other@smoke.example",
            "display_name": "Synthetic tester", "password": "synthetic-smoke-password",
        }).encode())["access_token"]
        document_id = uploaded["document"]["id"]
        assert all(doc["id"] != document_id for doc in request("/api/documents", token=other))
        try:
            request(f"/api/documents/{document_id}/pages", token=other)
        except HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("Cross-organization document access succeeded")
    documents = request("/api/documents", token=token)
    document, = [doc for doc in documents if doc["filename"] == "render-smoke.txt"]
    assert request(f'/api/documents/{document["id"]}/pages', token=token)
    original = Path(os.environ["UPLOAD_DIRECTORY"]) / document["storage_key"]
    assert original.read_bytes() == CONTENT
    print(json.dumps({"document_id": document["id"], "catalog_count": len(catalog)}))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    project = "contractfit-smoke-" + uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix="contractfit-smoke-") as temporary:
        env_file = Path(temporary) / "empty.env"
        env_file.write_text("")
        compose = ["docker", "compose", "--env-file", str(env_file), "-p", project,
                   "-f", str(root / "scripts/compose.render-smoke.yaml")]

        def run(*args: str, capture: bool = False, source: str | None = None) -> str:
            try:
                result = subprocess.run([*compose, *args], input=source, text=True,
                                        capture_output=capture, check=True, timeout=600, cwd=root)
            except subprocess.CalledProcessError as exc:
                if capture:
                    print(exc.stdout or "", file=sys.stderr)
                    print(exc.stderr or "", file=sys.stderr)
                raise
            return result.stdout.strip() if capture else ""

        script = Path(__file__).read_text()
        try:
            run("up", "-d", "--build")
            before = json.loads(run("exec", "-T", "api", "python", "-", "before",
                                    capture=True, source=script))
            current = run("exec", "-T", "api", "alembic", "current", capture=True)
            assert "20261106_0018" in current
            run("exec", "-T", "api", "alembic", "check")
            vector = run("exec", "-T", "db", "psql", "-U", "smoke", "-d", "render_smoke",
                         "-Atc", "SELECT extname FROM pg_extension WHERE extname = 'vector'", capture=True)
            assert vector == "vector"
            run("up", "-d", "--no-deps", "--force-recreate", "api")
            after = json.loads(run("exec", "-T", "api", "python", "-", "after",
                                   capture=True, source=script))
            assert before["document_id"] == after["document_id"]
            # The upload creates one opportunity in the first pass.
            assert after["catalog_count"] == before["catalog_count"] + 1
            print("Render container smoke passed: migrations, PORT, auth, inline upload, isolation, persistence.")
        except Exception:
            subprocess.run([*compose, "logs", "--no-color", "--tail", "200"],
                           check=False, timeout=30, cwd=root)
            raise
        finally:
            subprocess.run([*compose, "down", "--volumes", "--rmi", "local", "--remove-orphans"],
                           check=True, timeout=120, cwd=root)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        inside(sys.argv[1])
    else:
        main()
