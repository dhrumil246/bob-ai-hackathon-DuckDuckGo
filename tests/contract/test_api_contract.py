"""
Contract and behaviour snapshots for every HTTP endpoint. See README.md in this folder.

Two snapshots per request:

- **shape**: status code, content type, and the structure of the JSON body (keys and
  value types). A change here can break the web app, so it must never be accidental.
- **behaviour**: the JSON body itself, with values that legitimately change between
  runs (timings, timestamps, generated ids) masked. A change here means the system now
  answers differently. That may be the intent of a pull request, in which case the
  snapshots are regenerated on purpose and the diff is reviewed.

Regenerate with the "Tests" workflow's manual run (update_snapshots = true), or locally
with UPDATE_SNAPSHOTS=1. Tests run in CI; see docs/industry-readiness/PLAN.md.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SNAP_DIR = Path(__file__).parent / "snapshots"
SHAPES_FILE = SNAP_DIR / "shapes.json"
BEHAVIOUR_FILE = SNAP_DIR / "behaviour.json"
UPDATE = os.environ.get("UPDATE_SNAPSHOTS") == "1"

_LOTS = json.loads((ROOT / "src" / "mcp_server" / "data" / "lots.json").read_text())["lots"]
TESTED = [lid for lid, v in _LOTS.items() if v.get("status") == "tested"]
PLANNED = [lid for lid, v in _LOTS.items() if v.get("status") == "planned"]
UNKNOWN_LOT = "L-0000"

SAMPLES = ROOT / "samples"


# ── normalisation ──────────────────────────────────────────────────────────────

_VOLATILE_KEY = re.compile(
    r"(^|_)(ms|timestamp|ts|elapsed|latency|duration|created_at|recorded_at|"
    r"generated_at|uuid|run_id|hypothesis_id)$", re.IGNORECASE)
_VALUE_MASKS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?"), "<timestamp>"),
    (re.compile(r"\bH-[0-9a-f]{6}-\d+\b"), "<hypothesis_id>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "<uuid>"),
]


def _mask_str(s: str, tmp: str) -> str:
    s = s.replace(tmp, "<tmp>")
    for pattern, token in _VALUE_MASKS:
        s = pattern.sub(token, s)
    return s


def normalise(v, tmp: str, key: str = ""):
    """The body with run-to-run noise removed, for the behaviour snapshot."""
    if key and _VOLATILE_KEY.search(key):
        return "<volatile>"
    if isinstance(v, dict):
        return {k: normalise(v[k], tmp, k) for k in sorted(v)}
    if isinstance(v, list):
        return [normalise(x, tmp) for x in v]
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, float):
        r = round(v, 4)
        return 0.0 if r == 0 else r
    if isinstance(v, str):
        return _mask_str(v, tmp)
    return v


def _type(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "str"
    return type(v).__name__


def _union(a, b):
    """Merge two shapes, for lists whose elements differ."""
    if a == b:
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: _union(a.get(k, "absent"), b.get(k, "absent")) for k in sorted(set(a) | set(b))}
    if isinstance(a, list) and isinstance(b, list):
        if not a or not b:
            return a or b
        return [_union(a[0], b[0])]
    parts = set()
    for x in (a, b):
        parts.update(x.split("|") if isinstance(x, str) else [json.dumps(x, sort_keys=True)])
    return "|".join(sorted(parts))


def shape(v):
    """Keys and value types only: what the web app depends on."""
    if isinstance(v, dict):
        return {k: shape(v[k]) for k in sorted(v)}
    if isinstance(v, list):
        if not v:
            return []
        merged = shape(v[0])
        for x in v[1:]:
            merged = _union(merged, shape(x))
        return [merged]
    return _type(v)


# ── requests ───────────────────────────────────────────────────────────────────

def _first(obj, key):
    """First value stored under `key` anywhere in a JSON body."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        obj = list(obj.values())
    if isinstance(obj, list):
        for x in obj:
            found = _first(x, key)
            if found is not None:
                return found
    return None


def _sample(name: str) -> dict:
    return json.loads((SAMPLES / name).read_text())


def _upload(client, npy: str, sensor_json: str | None):
    meta = _sample(sensor_json) if sensor_json else {}
    with open(SAMPLES / npy, "rb") as f:
        return client.post(
            "/api/analyze-upload",
            files={"wafer_map": (npy, f.read(), "application/octet-stream")},
            data={"sensors": json.dumps(meta.get("sensor_signature", {})),
                  "equipment_ids": ",".join(meta.get("equipment_ids", [])),
                  "sample_id": meta.get("sample_id", "CONTRACT-TEST")})


def _with_failing_chain(api, call):
    """Run `call` while the MCP tool chain raises, to reach /api/chat's fallback path."""
    original = api.analyse

    def broken(*_args, **_kwargs):
        raise RuntimeError("tool chain unavailable (forced by contract test)")

    api.analyse = broken
    try:
        return call()
    finally:
        api.analyse = original


def _cases():
    """(case_id, function(client, api) -> response). Ids are stable snapshot keys."""
    c = []
    for path in ["/", "/api/status", "/api/lots", "/api/health", "/api/eval", "/api/equipment",
                 "/api/cases", "/api/metrics", "/api/cmp/runs", "/api/transparency",
                 "/api/pipeline/presets"]:
        c.append((f"GET {path}", lambda cl, a, p=path: cl.get(p)))

    for lot in TESTED + PLANNED + [UNKNOWN_LOT]:
        c.append((f"GET /api/analyze?lot={lot}", lambda cl, a, l=lot: cl.get("/api/analyze", params={"lot": l})))

    def cmp_predict(cl, gate):
        wafer = _first(cl.get("/api/cmp/runs").json(), "wafer_id")
        return cl.get("/api/cmp/predict", params={"wafer_id": wafer, "stage": "A", "gate": gate})
    c.append(("GET /api/cmp/predict gate=true", lambda cl, a: cmp_predict(cl, True)))
    c.append(("GET /api/cmp/predict gate=false", lambda cl, a: cmp_predict(cl, False)))
    c.append(("GET /api/cmp/predict unknown wafer",
              lambda cl, a: cl.get("/api/cmp/predict", params={"wafer_id": "no-such-wafer"})))

    lot0 = TESTED[0]
    c.append(("POST /api/prior-read", lambda cl, a: cl.post("/api/prior-read", json={
        "lot_id": lot0, "hypothesis": "etch chamber drift", "category": "equipment",
        "confidence": 60, "engineer": "contract-test"})))
    c.append(("GET /api/prior-read", lambda cl, a: cl.get("/api/prior-read", params={"lot": lot0})))
    c.append(("POST /api/disposition unknown hypothesis", lambda cl, a: cl.post("/api/disposition", json={
        "hypothesis_id": "H-000000-1", "verdict": "confirmed", "notes": "contract test"})))

    import numpy as np  # noqa: PLC0415
    defect = np.load(SAMPLES / "wafer_defect.npy").astype(int).tolist()
    empty = [[0] * 64 for _ in range(64)]
    c.append(("POST /api/vision/explain real wafer", lambda cl, a: cl.post("/api/vision/explain", json={"grid": defect})))
    c.append(("POST /api/vision/explain empty grid", lambda cl, a: cl.post("/api/vision/explain", json={"grid": empty})))

    c.append(("POST /api/pipeline/run-custom no wafer", lambda cl, a: cl.post("/api/pipeline/run-custom", json={})))
    c.append(("POST /api/pipeline/run-custom empty grid",
              lambda cl, a: cl.post("/api/pipeline/run-custom", json={"wafer_grid": empty})))
    c.append(("POST /api/pipeline/run-custom real wafer",
              lambda cl, a: cl.post("/api/pipeline/run-custom", json={"wafer_grid": defect})))

    def run_preset(cl, index):
        body = cl.get("/api/pipeline/presets").json()
        presets = body.get("presets", body) if isinstance(body, dict) else body
        return cl.post("/api/pipeline/run-custom", json={"case_id": presets[index]["case_id"]})
    for i in range(6):
        c.append((f"POST /api/pipeline/run-custom preset[{i}]", lambda cl, a, i=i: run_preset(cl, i)))

    c.append(("POST /api/analyze-upload defect sample",
              lambda cl, a: _upload(cl, "wafer_defect.npy", "sensors_defect.json")))
    c.append(("POST /api/analyze-upload clean sample",
              lambda cl, a: _upload(cl, "wafer_clean.npy", "sensors_clean.json")))

    planned0 = PLANNED[0]
    chat = [
        ("tested lot", {"message": "Why did this lot fail?", "lot_id": lot0}),
        ("planned lot", {"message": "Is this lot at risk?", "lot_id": planned0}),
        ("unknown lot", {"message": f"What happened to {UNKNOWN_LOT}?", "lot_id": UNKNOWN_LOT}),
        ("next steps", {"message": "What should I do next?", "lot_id": lot0}),
    ]
    for name, body in chat:
        c.append((f"POST /api/chat {name}", lambda cl, a, b=body: cl.post("/api/chat", json=b)))
    # The fallback path: reached only when the MCP tool chain itself fails.
    for name, body in [chat[0], chat[1], chat[3]]:
        c.append((f"POST /api/chat {name}, tool chain failing",
                  lambda cl, a, b=body: _with_failing_chain(a, lambda: cl.post("/api/chat", json=b))))
    return c


CASES = _cases()


# ── recording ──────────────────────────────────────────────────────────────────

def _record(resp, tmp: str) -> tuple[dict, dict]:
    ctype = (resp.headers.get("content-type") or "").split(";")[0].strip()
    head = {"status": resp.status_code, "content_type": ctype}
    if ctype == "application/json":
        body = resp.json()
        return {**head, "body": shape(body)}, {**head, "body": normalise(body, tmp)}
    return head, head          # HTML and text: only status and type are part of the contract


@pytest.fixture(scope="session")
def observed(client, api, tmp_store_dir):
    tmp = str(tmp_store_dir)
    shapes, behaviour = {}, {}
    for case_id, call in CASES:
        shapes[case_id], behaviour[case_id] = _record(call(client, api), tmp)
    if UPDATE:
        SNAP_DIR.mkdir(exist_ok=True)
        SHAPES_FILE.write_text(json.dumps(shapes, indent=1, sort_keys=True) + "\n")
        BEHAVIOUR_FILE.write_text(json.dumps(behaviour, indent=1, sort_keys=True) + "\n")
    return shapes, behaviour


def _load(path: Path) -> dict:
    if not path.exists():
        pytest.fail(f"{path.relative_to(ROOT)} is missing. Generate it with the 'Tests' workflow "
                    "(Run workflow, update_snapshots = true).")
    return json.loads(path.read_text())


def _first_difference(expected, actual, path="$"):
    if type(expected) is not type(actual):
        return f"{path}: expected {json.dumps(expected)[:200]}, got {json.dumps(actual)[:200]}"
    if isinstance(expected, dict):
        for k in sorted(set(expected) | set(actual)):
            if k not in actual:
                return f"{path}.{k}: missing (was {json.dumps(expected[k])[:120]})"
            if k not in expected:
                return f"{path}.{k}: new field {json.dumps(actual[k])[:120]}"
            d = _first_difference(expected[k], actual[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: length {len(expected)} -> {len(actual)}"
        for i, (e, a) in enumerate(zip(expected, actual)):
            d = _first_difference(e, a, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if expected == actual else f"{path}: {json.dumps(expected)[:200]} -> {json.dumps(actual)[:200]}"


IDS = [case_id for case_id, _ in CASES]


@pytest.mark.parametrize("case_id", IDS)
def test_shape(case_id, observed):
    if UPDATE:
        pytest.skip("regenerating snapshots")
    expected = _load(SHAPES_FILE)
    assert case_id in expected, f"new case {case_id!r}: regenerate the snapshots"
    diff = _first_difference(expected[case_id], observed[0][case_id])
    assert diff is None, f"response SHAPE changed — this can break the web app. {diff}"


@pytest.mark.parametrize("case_id", IDS)
def test_behaviour(case_id, observed):
    if UPDATE:
        pytest.skip("regenerating snapshots")
    expected = _load(BEHAVIOUR_FILE)
    assert case_id in expected, f"new case {case_id!r}: regenerate the snapshots"
    diff = _first_difference(expected[case_id], observed[1][case_id])
    assert diff is None, (f"response BEHAVIOUR changed. If intended, regenerate the snapshots "
                          f"and explain the change in the pull request. {diff}")


def test_no_stale_cases():
    """Every snapshot entry still has a matching request, so removed cases are noticed."""
    if UPDATE:
        pytest.skip("regenerating snapshots")
    stale = sorted(set(_load(SHAPES_FILE)) - set(IDS))
    assert not stale, f"snapshot entries with no request: {stale}"


def test_stores_stay_out_of_the_repo(observed, tmp_store_dir):
    """The POST cases above must have written to the temporary folder, not the repo."""
    assert (tmp_store_dir / "prior_reads.jsonl").exists(), "prior-read store not redirected"
