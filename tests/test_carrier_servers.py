"""Unit tests for Carrier HTTP API endpoints (Ports 8005, 8006, 8007)."""

import json
from pathlib import Path
from starlette.testclient import TestClient

from simulators.type_c.server import create_carrier_app, DATA_DIR
from simulators.type_c.scheduler import LATEST_STATE


def test_carrier_endpoints(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("simulators.type_c.server.DATA_DIR", tmp_path)

    # Prepare dummy files in tmp_path
    (tmp_path / "carrier_1_latest.csv").write_text("id,status\n1,DELIVERED\n", encoding="utf-8")
    (tmp_path / "carrier_1_latest.json").write_text(json.dumps([{"id": 1, "status": "DELIVERED"}]), encoding="utf-8")

    (tmp_path / "carrier_2_latest.xlsx").write_bytes(b"dummy_excel_bytes")
    (tmp_path / "carrier_2_latest.json").write_text(json.dumps([{"id": 2, "status": "EN_TRANSITO"}]), encoding="utf-8")

    (tmp_path / "carrier_3_latest.csv").write_text("id,estado\n1,30\n", encoding="utf-8")
    (tmp_path / "carrier_3_latest.json").write_text(json.dumps([{"id": 3, "estado": 30}]), encoding="utf-8")

    LATEST_STATE["cycle_id"] = "cycle-test-123"
    LATEST_STATE["carriers"][1] = {"rows_generated": 1, "sha256": "abc1"}
    LATEST_STATE["carriers"][2] = {"rows_generated": 1, "sha256": "abc2"}
    LATEST_STATE["carriers"][3] = {"rows_generated": 1, "sha256": "abc3"}

    # Test Carrier 1
    app1 = create_carrier_app(1)
    client1 = TestClient(app1)

    r1_info = client1.get("/")
    assert r1_info.status_code == 200
    assert r1_info.json()["carrier_id"] == 1
    assert r1_info.json()["format"] == "csv"

    r1_health = client1.get("/health")
    assert r1_health.status_code == 200
    assert r1_health.json()["status"] == "healthy"

    r1_download = client1.get("/download")
    assert r1_download.status_code == 200
    assert "text/csv" in r1_download.headers["content-type"]
    assert b"id,status" in r1_download.content

    r1_events = client1.get("/events")
    assert r1_events.status_code == 200
    assert r1_events.json()["count"] == 1

    # Test Carrier 2
    app2 = create_carrier_app(2)
    client2 = TestClient(app2)

    r2_info = client2.get("/")
    assert r2_info.status_code == 200
    assert r2_info.json()["carrier_id"] == 2
    assert r2_info.json()["format"] == "xlsx"

    r2_download = client2.get("/download")
    assert r2_download.status_code == 200
    assert r2_download.content == b"dummy_excel_bytes"

    # Test Carrier 3
    app3 = create_carrier_app(3)
    client3 = TestClient(app3)

    r3_info = client3.get("/")
    assert r3_info.status_code == 200
    assert r3_info.json()["carrier_id"] == 3

    r3_download = client3.get("/download")
    assert r3_download.status_code == 200
    assert b"1,30" in r3_download.content
