"""
Environment for the API contract tests. Runs before the API module is imported.

- The mock LLM is forced, and provider keys are removed: tests never spend quota and
  never depend on a model provider being up.
- Outbound network connections are blocked: anything that tries to reach the internet
  fails loudly instead of silently changing behaviour.
- The feedback and prior-read stores write to a temporary folder, so the tests leave
  no records in the repository.
"""
from __future__ import annotations

import os
import socket
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="yieldguard-contract-"))

os.environ["USE_MOCK_LLM"] = "true"
for _key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "WATSONX_API_KEY", "BOB_API_KEY"):
    os.environ.pop(_key, None)
os.environ["YIELDGUARD_FEEDBACK_PATH"] = str(TMP / "feedback.jsonl")
os.environ["YIELDGUARD_PRIOR_PATH"] = str(TMP / "prior_reads.jsonl")

sys.path.insert(0, str(ROOT / "src" / "api"))


_real_connect = socket.socket.connect


def _guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if isinstance(host, str) and (host in ("localhost", "127.0.0.1", "::1") or host.startswith("/")):
        return _real_connect(self, address)
    raise RuntimeError(f"contract tests must not reach the network (tried {address!r})")


socket.socket.connect = _guarded_connect


@pytest.fixture(scope="session")
def api():
    """The FastAPI module, imported once under the environment above."""
    import main  # noqa: PLC0415  (import after the environment is set)

    assert os.environ.get("USE_MOCK_LLM") == "true", "a .env file overrode the mock LLM"
    return main


@pytest.fixture(scope="session")
def client(api):
    from fastapi.testclient import TestClient  # noqa: PLC0415

    return TestClient(api.app)


@pytest.fixture(scope="session")
def tmp_store_dir():
    return TMP
