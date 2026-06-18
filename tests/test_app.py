import json
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def build_client(tmp_path, monkeypatch):
    feedback_dir = tmp_path / "feedback"
    monkeypatch.setenv("PHISHGUARD_FEEDBACK_DIR", str(feedback_dir))

    if "app" in sys.modules:
        del sys.modules["app"]

    import app as app_module

    return app_module.app.test_client(), feedback_dir


# ─── API Endpoint Tests ────────────────────────────


def test_homepage_loads(tmp_path, monkeypatch):
    client, _ = build_client(tmp_path, monkeypatch)
    response = client.get("/")
    assert response.status_code == 200
    assert "PhishGuard" in response.get_data(as_text=True)


def test_get_email_returns_payload(tmp_path, monkeypatch):
    """Verify /get-email returns a valid payload.

    We mock generate_ai_email so this test works without live API keys.
    The mock simulates a successful Gemini+Llama consensus result.
    """
    client, _ = build_client(tmp_path, monkeypatch)
    mock_email = {
        "text": "Your account has been suspended. Click here to restore access immediately.",
        "label": "phishing",
        "_validated": True,
        "_consensus_round": 1,
    }
    with patch("app.generate_ai_email", return_value=(mock_email, None)):
        response = client.get("/get-email")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["text"]
    assert payload["label"] in {"phishing", "legitimate"}
    # Consensus metadata must be present
    assert "_validated" in payload
    assert "_consensus_round" in payload


def test_get_email_returns_503_when_ai_fails(tmp_path, monkeypatch):
    """If all AI attempts fail, /get-email must return 503 — no silent dataset fallback."""
    client, _ = build_client(tmp_path, monkeypatch)
    with patch("app.generate_ai_email", return_value=(None, "AI unavailable")):
        response = client.get("/get-email")

    assert response.status_code == 503
    payload = response.get_json()
    assert "error" in payload


def test_submit_feedback_persists_file(tmp_path, monkeypatch):
    client, feedback_dir = build_client(tmp_path, monkeypatch)
    response = client.post("/submit-feedback", json={"feedback": "Great flow"})
    assert response.status_code == 200
    assert feedback_dir.exists()
    assert any(feedback_dir.iterdir())


def test_health_endpoint(tmp_path, monkeypatch):
    client, _ = build_client(tmp_path, monkeypatch)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_submit_feedback_rejects_empty(tmp_path, monkeypatch):
    """Empty feedback must be rejected with 400."""
    client, _ = build_client(tmp_path, monkeypatch)
    response = client.post("/submit-feedback", json={"feedback": ""})
    assert response.status_code == 400


def test_submit_feedback_rejects_too_long(tmp_path, monkeypatch):
    """Feedback exceeding the max length must be rejected with 400."""
    client, _ = build_client(tmp_path, monkeypatch)
    long_text = "x" * 1001
    response = client.post("/submit-feedback", json={"feedback": long_text})
    assert response.status_code == 400

