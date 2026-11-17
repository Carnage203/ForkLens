"""API integration tests: in-memory SQLite, mock AI providers, no network."""
from __future__ import annotations

import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.db.models import CacheEntry, Event
from backend.db.session import Database
from backend.main import create_app
from backend.services.cache import DbCache
from backend.services.limiter import DbRateLimiter
from backend.services.supabase_auth import AuthUser
from snap2cook.config import Settings
from snap2cook.exceptions import RateLimitExceededError

GUEST = {"X-Client-Id": "guest-client-0001-abcdef"}
ADMIN = {"username": "boss", "password": "correct-horse-battery"}


def make_settings(tmp_path, **kw) -> Settings:
    return Settings(cache_dir=tmp_path / "cache", log_dir=tmp_path / "logs", admin_username="boss",
                    admin_password="correct-horse-battery", admin_jwt_secret="s" * 40, **kw)


@pytest.fixture()
def client(tmp_path):
    app = create_app(make_settings(tmp_path), Database("sqlite://"))
    with TestClient(app) as test_client:
        yield test_client


def photo() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 120, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


def recipe_body(**kw) -> dict:
    return {"ingredients": ["oats", "banana"], "tier": "hostel", **kw}


def test_health_and_config(client):
    assert client.get("/api/health").json()["db"] is True
    cfg = client.get("/api/config").json()
    assert cfg["mode"] == "mock" and "milk" in cfg["extras"] and cfg["auth"]["enabled"] is False


def test_missing_client_id_is_rejected_with_envelope(client):
    body = client.get("/api/saved").json()
    assert body["error"]["code"] == "http_error"


def test_scan_and_generate_flow(client):
    scan = client.post("/api/scan", headers=GUEST, files=[("files", ("a.jpg", photo(), "image/jpeg"))])
    assert scan.status_code == 200 and scan.json()["ingredients"]
    run = client.post("/api/recipes/generate", headers=GUEST, json=recipe_body())
    data = run.json()
    assert run.status_code == 200 and data["run_id"] and data["recipe"]["title"]
    assert data["recipe"]["meta"]["calories"] > 0
    assert len(client.get("/api/history", headers=GUEST).json()) == 1


def test_invalid_image_gets_friendly_error(client):
    response = client.post("/api/scan", headers=GUEST, files=[("files", ("a.jpg", b"not an image", "image/jpeg"))])
    assert response.status_code == 400 and response.json()["error"]["code"] == "invalid_image"


def test_generate_validates_input(client):
    assert client.post("/api/recipes/generate", headers=GUEST, json={"ingredients": [], "tier": "home"}).status_code == 422
    assert client.post("/api/recipes/generate", headers=GUEST, json={"ingredients": ["egg"], "tier": "castle"}).status_code == 422


def test_guest_rate_limit_returns_429(tmp_path):
    app = create_app(make_settings(tmp_path, guest_gen_limit=2), Database("sqlite://"))
    with TestClient(app) as c:
        codes = [c.post("/api/recipes/generate", headers=GUEST,
                        json={"ingredients": [name], "tier": "home", "equipment": ["gas_stove"]}).status_code
                 for name in ("egg", "rice", "bread")]
    assert codes == [200, 200, 429]


def test_saved_share_and_cooked(client):
    recipe = client.post("/api/recipes/generate", headers=GUEST, json=recipe_body()).json()["recipe"]
    saved = client.post("/api/saved", headers=GUEST, json={"recipe": recipe, "tier": "hostel"})
    assert saved.status_code == 201
    saved_id = saved.json()["id"]
    assert client.post("/api/saved", headers=GUEST, json={"recipe": recipe, "tier": "hostel"}).json()["id"] == saved_id
    assert client.post(f"/api/saved/{saved_id}/cooked", headers=GUEST).json()["cooked_count"] == 1
    token = client.post(f"/api/saved/{saved_id}/share", headers=GUEST, json={"enabled": True}).json()["share_token"]
    assert client.get(f"/api/shared/{token}").json()["title"] == recipe["title"]
    client.post(f"/api/saved/{saved_id}/share", headers=GUEST, json={"enabled": False})
    assert client.get(f"/api/shared/{token}").status_code == 404
    me = client.get("/api/me", headers=GUEST).json()
    assert me["stats"]["cooked"] == 1 and me["stats"]["streak"] == 1
    other = {"X-Client-Id": "another-guest-000000-xyz"}
    assert client.delete(f"/api/saved/{saved_id}", headers=other).status_code == 404  # not yours
    assert client.delete(f"/api/saved/{saved_id}", headers=GUEST).status_code == 204


def test_pantry_and_shopping(client):
    assert client.put("/api/pantry", headers=GUEST, json={"items": [{"name": "Rice"}, {"name": "rice"}, {"name": "Egg"}]}).json() \
        == [{"name": "egg", "use_by": None}, {"name": "rice", "use_by": None}]
    items = client.post("/api/shopping", headers=GUEST, json={"names": ["Milk", "milk", "oil"]}).json()
    assert sorted(i["name"] for i in items) == ["milk", "oil"]
    milk = next(i for i in items if i["name"] == "milk")
    assert client.patch(f"/api/shopping/{milk['id']}", headers=GUEST, json={"checked": True}).json()["checked"] is True
    client.delete("/api/shopping", headers=GUEST)
    assert [i["name"] for i in client.get("/api/shopping", headers=GUEST).json()] == ["oil"]


def test_claim_moves_guest_data_to_account(tmp_path):
    app = create_app(make_settings(tmp_path), Database("sqlite://"))
    with TestClient(app) as c:
        c.put("/api/pantry", headers=GUEST, json={"items": [{"name": "rice"}]})
        services = app.state.hub.services
        object.__setattr__(services, "verifier", type("V", (), {"verify": lambda self, t: AuthUser("user-1", "a@b.co", "Ann")})())
        signed_in = {**GUEST, "Authorization": "Bearer fake-token"}
        assert c.post("/api/me/claim", headers=signed_in).json()["moved"] == 1
        assert c.get("/api/pantry", headers=signed_in).json() == [{"name": "rice", "use_by": None}]
        assert c.get("/api/pantry", headers=GUEST).json() == []
        assert c.get("/api/me", headers=signed_in).json()["kind"] == "user"


def test_admin_is_hidden_then_login_unlocks_dashboard(client):
    assert client.get("/api/admin/overview").status_code == 404
    assert client.get("/api/admin/session").status_code == 404
    assert client.post("/api/admin/login", json={"username": "boss", "password": "nope"}).status_code == 401
    assert client.post("/api/admin/login", json=ADMIN).status_code == 200
    client.post("/api/recipes/generate", headers=GUEST, json=recipe_body())
    overview = client.get("/api/admin/overview?days=7").json()
    assert overview["users"]["total"] >= 1 and len(overview["series"]) == 7
    assert overview["recipes"]["total"] == 1 and overview["requests"]["total"] >= 1
    rows = client.get("/api/admin/requests?path=generate").json()["rows"]
    assert rows and rows[0]["status"] == 200
    assert client.get("/api/admin/users").json()["total"] >= 1
    assert "gemini" in client.get("/api/admin/system").json()["keys"]
    client.post("/api/admin/logout")
    assert client.get("/api/admin/overview").status_code == 404


def test_admin_login_locks_out_after_repeated_failures(client):
    codes = [client.post("/api/admin/login", json={"username": "boss", "password": "bad"}).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]
    assert client.post("/api/admin/login", json=ADMIN).status_code == 429


def test_admin_disabled_without_secret(tmp_path):
    settings = Settings(cache_dir=tmp_path / "c", log_dir=tmp_path / "l")
    with TestClient(create_app(settings, Database("sqlite://"))) as c:
        assert c.post("/api/admin/login", json=ADMIN).status_code == 404


def test_cron_requires_secret(tmp_path):
    app = create_app(make_settings(tmp_path, cron_secret="cron-secret-value"), Database("sqlite://"))
    with TestClient(app) as c:
        assert c.get("/api/cron/cleanup").status_code == 404
        assert c.get("/api/cron/cleanup", headers={"Authorization": "Bearer cron-secret-value"}).status_code == 200


def test_db_cache_roundtrip_and_expiry():
    db = Database("sqlite://")
    db.create_all()
    now = [1000.0]
    cache = DbCache(db, clock=lambda: now[0])
    cache.set("k", {"a": [1, 2]}, ttl=10)
    assert cache.get("k") == {"a": [1, 2]}
    now[0] += 11
    assert cache.get("k") is None and cache.purge_expired() == 1


def test_db_limiter_distinguishes_guests_and_users():
    db = Database("sqlite://")
    db.create_all()
    limiter = DbRateLimiter(db, "generation", guest_limit=1, user_limit=3, window_s=600, daily_max=100)
    limiter.check("g_abc|ip1")
    with pytest.raises(RateLimitExceededError) as caught:
        limiter.check("g_abc|ip1")
    assert caught.value.retry_after > 0
    for _ in range(3):
        limiter.check("user-9|ip2")
    with pytest.raises(RateLimitExceededError):
        limiter.check("user-9|ip2")
    with db.session() as session:
        assert session.query(Event).filter_by(type="quota:generation").count() == 4


def test_request_log_records_errors_and_ids(client):
    response = client.post("/api/recipes/generate", headers=GUEST, json={"ingredients": [], "tier": "home"})
    assert response.headers["x-request-id"]
    client.post("/api/admin/login", json=ADMIN)
    rows = client.get("/api/admin/requests?min_status=400").json()["rows"]
    assert rows[0]["status"] == 422 and rows[0]["error"].startswith("invalid_request")
    assert time.time() > 0 and CacheEntry.__tablename__ == "cache_entries"
