import json
import urllib.request

BASE = "http://127.0.0.1:8002"
tests = []

def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return r.status, json.loads(r.read())

def post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read())

status, data = get("/health")
assert status == 200
assert data["segments_loaded"] == 19628
assert data["model_version"] == "0.2-research-preview"
tests.append("PASS  health")

status, data = get("/v1/segments/13970")
assert data["validation"]["in_validation_cohort"] is True
assert data["structural_context"]["percentile"] == 98.62
tests.append("PASS  validated segment 13970")

status, data = get("/v1/segments/32")
assert data["validation"]["in_validation_cohort"] is False
assert data["structural_context"]["percentile"] is None
tests.append("PASS  outside-cohort segment 32")

status, data = get(
    "/v1/road-context?lat=40.4406&lon=-79.9959"
)
assert data["segment_id"] == 13355
assert data["validation"]["in_validation_cohort"] is False
tests.append("PASS  full-network coordinate lookup")

status, data = post(
    "/v1/route-context",
    {
        "points": [
            {"lat": 40.4406, "lon": -79.9959},
            {"lat": 40.4408, "lon": -79.9955},
            {"lat": 40.4410, "lon": -79.9950},
        ]
    },
)

rc = data["route_context"]
assert rc["points_matched"] == 3
assert rc["validated_segments"] == 2
assert rc["outside_validation_cohort"] == 1
assert rc["maximum_validated_structural_percentile"] == 98.62
tests.append("PASS  mixed route")

print("\nPRAEDICTA API v0.2 REGRESSION TEST")
print("=" * 42)
for test in tests:
    print(test)
print("=" * 42)
print(f"RESULT: {len(tests)}/{len(tests)} TESTS PASSED")
