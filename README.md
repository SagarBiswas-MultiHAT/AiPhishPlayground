# PhishGuard - Email Phishing Detection

<div align="right">

[![CI](https://img.shields.io/github/actions/workflow/status/SagarBiswas-MultiHAT/Ai-Phishy-Playground/get-started-with-github-actions.yml?branch=main)](https://github.com/SagarBiswas-MultiHAT/Ai-Phishy-Playground/actions)
&nbsp;
![Tests](https://img.shields.io/badge/tests-pytest-brightgreen)
&nbsp;
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
&nbsp;
![License](https://img.shields.io/github/license/SagarBiswas-MultiHAT/Ai-Phishy-Playground)
&nbsp;
![Ruff](https://img.shields.io/badge/lint-ruff-101010)

</div>

PhishGuard is a fast, game-like phishing awareness trainer. It serves one short message at a time, asks the user to decide whether it is phishing or legitimate, and tracks score in real time. The project is intentionally lightweight so it can run locally, in workshops, or as a demo for security awareness.

---

![](https://imgur.com/MttZMLQ.png)

---

## Features

- **Interactive classification** with a 10-second timer per message.
- **Score + attempts tracking** to measure progress.
- **AI Challenge mode** to generate new samples on demand.
- **Feedback capture** stored locally as JSON.
- **Safety checks** on payload size and input validation.

## Why this exists

Phishing is still the easiest way to get into most organizations. PhishGuard turns common phishing patterns into quick, repeatable practice that helps people build stronger instincts without needing a large training platform.

## What you get

- **AI-generated scenarios**: Fresh, realistic messages crafted by an LLM.
- **Balanced labels**: Each round randomly chooses whether the next message is phishing or legitimate.
- **Strict validation**: The app only accepts AI responses that match the requested label and valid JSON shape.
- **Timer and scoring**: Ten-second countdown with score and attempt tracking.
- **Pause control**: Users can pause and resume the timer during a round.
- **Feedback capture**: Short feedback is saved locally for later review.
- **Dataset growth**: Accepted AI messages are appended to `phishing_data.json` for future exploration.

## How it works

1. The frontend calls `GET /get-email`.
2. The backend requests a new message from Groq with a randomly chosen label (phishing or legit).
3. The response is validated for structure and label accuracy.
4. The message is returned to the browser and appended to `phishing_data.json`.

If the AI response fails validation after retries, the backend falls back to a stored message (if available). This keeps the quiz responsive while preserving label accuracy.

## Project structure

```
phishguard/
├── app.py                 # Flask backend
├── phishing_data.json     # Dataset of labeled messages
├── FeedBack/              # Saved feedback submissions
├── static/
│   ├── script.js          # Frontend behavior
│   └── style.css          # UI styling
├── templates/
│   └── index.html         # Main UI template
├── tests/                 # Pytest suite
└── README.md
```

## Requirements

- Python 3.11+ recommended (3.8+ should work for Flask)
- Gemini API key (primary) and Groq API key (fallback) for AI generation

Python packages:

- `Flask`
- `groq`
- `google-genai`

## Setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
& ".venv/Scripts/Activate.ps1"
pip install -r requirements.txt
pip install -r requirements-ai.txt
```

Set the API keys (PowerShell):

```powershell
$env:GEMINI_API_KEY = "your_gemini_api_key_here"
$env:GROQ_API_KEY = "your_groq_api_key_here"
```

## Run the app

```powershell
python app.py
```

Open:

```
http://127.0.0.1:5000
```

## API endpoints

- `GET /` renders the UI.
- `GET /get-email` returns a newly generated message.
- `POST /submit-feedback` stores feedback locally.
- `GET /health` provides a simple health check.

## Configuration

Optional environment variables:

- `PHISHGUARD_DATA_PATH` (default: `phishing_data.json`)
- `PHISHGUARD_FEEDBACK_DIR` (default: `FeedBack/`)
- `PHISHGUARD_MAX_EMAIL` (default: `600` characters)
- `PHISHGUARD_MAX_DATASET` (default: `2000` entries)
- `PHISHGUARD_MAX_FEEDBACK` (default: `1000` characters)
- `PHISHGUARD_MIN_FEEDBACK_INTERVAL` (default: `2.0` seconds)

## Accuracy notes

PhishGuard does not guess or classify on its own. The quiz is accurate because:

- The backend requests a specific label on every AI generation.
- AI responses are rejected unless the label exactly matches the request.
- Stored dataset entries preserve their labels exactly as saved.

This ensures the correct answer in the quiz always matches the displayed label.

## Troubleshooting

- **500/503 on `/get-email`**: Check `GEMINI_API_KEY`, `GROQ_API_KEY`, and network access.
- **ModuleNotFoundError**: Activate the venv and install requirements.
- **CI failures**: Run `ruff check .` and `pytest` locally.

## Tests

```powershell
pytest
```

## License

MIT

## Contributing

Issues and pull requests are welcome. If you add new scenarios or UI ideas, please include a short explanation of the learning goal.

## License

MIT License.