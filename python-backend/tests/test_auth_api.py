from fastapi.testclient import TestClient

import main
from enterprise_support.auth_api import _safe_return_to


def test_safe_return_to_rejects_external_targets() -> None:
    assert _safe_return_to("/admin/workspace") == "/admin/workspace"
    assert _safe_return_to("https://example.com/admin") == "/support"
    assert _safe_return_to("//example.com/admin") == "/support"
    assert _safe_return_to(None) == "/support"


def test_oidc_login_is_disabled_in_dev_mode(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "dev")

    response = TestClient(main.app).get(
        "/auth/login?return_to=/admin/workspace",
        follow_redirects=False,
    )

    assert response.status_code == 404


def test_logout_clears_session_and_redirects_to_safe_path(monkeypatch) -> None:
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://localhost:3000")
    response = TestClient(main.app).post(
        "/auth/logout?return_to=/admin/login",
        follow_redirects=False,
        cookies={"enterprise_session": "session-token"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:3000/admin/login"
    assert "enterprise_session" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_logout_rejects_external_return_path(monkeypatch) -> None:
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://localhost:3000")
    response = TestClient(main.app).get(
        "/auth/logout?return_to=//evil.example",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:3000/support"
