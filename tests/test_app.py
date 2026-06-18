import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "phishing_data.json"


def build_client(tmp_path, monkeypatch):
    data_path = tmp_path / "data.json"
    data_path.write_text(
        json.dumps([{"text": "Test message from IT support.", "label": "legitimate"}])
    )
    feedback_dir = tmp_path / "feedback"

    monkeypatch.setenv("PHISHGUARD_DATA_PATH", str(data_path))
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
    client, _ = build_client(tmp_path, monkeypatch)
    response = client.get("/get-email")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["text"]
    assert payload["label"] in {"phishing", "legitimate"}


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


# ─── Dataset Integrity Tests ──────────────────────


def _load_dataset():
    """Load the production phishing_data.json file."""
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_dataset_is_valid_json():
    """The dataset file must be parseable JSON."""
    data = _load_dataset()
    assert isinstance(data, list), "Dataset root must be a JSON array"
    assert len(data) > 0, "Dataset must not be empty"


def test_dataset_schema():
    """Every entry must have exactly 'text' and 'label' keys."""
    data = _load_dataset()
    for i, entry in enumerate(data):
        assert isinstance(entry, dict), f"Entry {i} is not a dict"
        assert set(entry.keys()) == {"text", "label"}, (
            f"Entry {i} has unexpected keys: {set(entry.keys())}"
        )


def test_dataset_labels_are_valid():
    """Every label must be exactly 'phishing' or 'legitimate'."""
    data = _load_dataset()
    valid_labels = {"phishing", "legitimate"}
    for i, entry in enumerate(data):
        assert entry["label"] in valid_labels, (
            f"Entry {i} has invalid label '{entry['label']}'. "
            f"Must be one of {valid_labels}"
        )


def test_dataset_no_legacy_legit_label():
    """The legacy 'legit' label must not appear anywhere in the dataset."""
    data = _load_dataset()
    for i, entry in enumerate(data):
        assert entry["label"] != "legit", (
            f"Entry {i} uses deprecated 'legit' label. Use 'legitimate' instead."
        )


def test_dataset_no_empty_text():
    """Every entry must have non-empty text."""
    data = _load_dataset()
    for i, entry in enumerate(data):
        text = entry.get("text", "").strip()
        assert len(text) > 0, f"Entry {i} has empty text"


def test_dataset_minimum_text_length():
    """Every text must be at least 30 characters to be a meaningful example."""
    data = _load_dataset()
    for i, entry in enumerate(data):
        text = entry.get("text", "").strip()
        assert len(text) >= 30, (
            f"Entry {i} text is too short ({len(text)} chars): '{text[:50]}...'"
        )


def test_dataset_no_duplicate_texts():
    """No two entries should have exactly the same text."""
    data = _load_dataset()
    texts = [entry["text"].strip().lower() for entry in data]
    seen = set()
    for i, text in enumerate(texts):
        assert text not in seen, (
            f"Entry {i} is a duplicate: '{text[:60]}...'"
        )
        seen.add(text)


def test_dataset_label_balance():
    """Dataset should be roughly balanced (neither label exceeds 70% of total)."""
    data = _load_dataset()
    total = len(data)
    phishing_count = sum(1 for e in data if e["label"] == "phishing")
    legitimate_count = total - phishing_count

    max_ratio = 0.70
    assert phishing_count / total <= max_ratio, (
        f"Phishing examples ({phishing_count}/{total}) exceed {max_ratio:.0%} threshold"
    )
    assert legitimate_count / total <= max_ratio, (
        f"Legitimate examples ({legitimate_count}/{total}) exceed {max_ratio:.0%} threshold"
    )


def test_dataset_no_example_dot_com_in_phishing():
    """Phishing examples should use realistic fake domains, not 'example.com'."""
    data = _load_dataset()
    for i, entry in enumerate(data):
        if entry["label"] == "phishing":
            assert "example.com" not in entry["text"].lower(), (
                f"Phishing entry {i} uses generic 'example.com' — "
                f"use a realistic typosquat domain instead"
            )
