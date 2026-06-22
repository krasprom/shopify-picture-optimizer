from fastapi.testclient import TestClient
import app as app_module

client = TestClient(app_module.app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_fetch_image_disables_verify_only_for_admin2(monkeypatch):
    captured = {}
    class FakeResp:
        content = b"bytes"
        def raise_for_status(self): pass
    monkeypatch.setattr(app_module.requests, "get",
                        lambda url, timeout, verify, headers: (captured.update(verify=verify), FakeResp())[1])
    app_module.fetch_image("https://admin2.hardware-best.de/x.jpg")
    assert captured["verify"] is False
    app_module.fetch_image("https://cdn.shopify.com/x.jpg")
    assert captured["verify"] is True


def test_optimize_miss_then_hit(monkeypatch, tmp_path):
    app_module.CACHE_DIR = tmp_path
    calls = {"n": 0}
    monkeypatch.setattr(app_module, "fetch_image", lambda url: b"SRC")
    def fake_core(data, size, padding, fmt, session):
        calls["n"] += 1
        return b"OPTIMIZED", True
    monkeypatch.setattr(app_module, "optimize_bytes", fake_core)
    c = TestClient(app_module.app)
    r1 = c.post("/optimize", json={"url": "https://x/y.jpg"})
    assert r1.status_code == 200 and r1.content == b"OPTIMIZED"
    assert r1.headers["X-Cache"] == "miss" and r1.headers["X-Object-Detected"] == "true"
    r2 = c.post("/optimize", json={"url": "https://x/y.jpg"})
    assert r2.headers["X-Cache"] == "hit" and calls["n"] == 1


def test_optimize_download_failure_returns_502(monkeypatch, tmp_path):
    app_module.CACHE_DIR = tmp_path
    def boom(url): raise RuntimeError("nope")
    monkeypatch.setattr(app_module, "fetch_image", boom)
    r = TestClient(app_module.app).post("/optimize", json={"url": "https://x/y.jpg"})
    assert r.status_code == 502
