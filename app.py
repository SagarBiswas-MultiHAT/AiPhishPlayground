import json
import os
import random
import re
import threading
import time

from flask import Flask, jsonify, render_template, request

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None

try:
    from groq import Groq
except Exception:
    Groq = None

DEFAULT_MAX_FEEDBACK_LENGTH = 1000
DEFAULT_MAX_EMAIL_LENGTH = 600
DEFAULT_MAX_DATASET_SIZE = 2000
DEFAULT_MIN_FEEDBACK_INTERVAL = 2.0


def load_emails(data_path):
    try:
        with open(data_path, encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, list) else []
    except FileNotFoundError:
        print("Error: phishing_data.json file not found.")
        return []
    except json.JSONDecodeError:
        print("Error: Failed to parse phishing_data.json.")
        return []


def save_emails(data_path, updated_emails):
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(updated_emails, handle, indent=2, ensure_ascii=False)


def json_error(message, status=400):
    return jsonify({"error": message}), status


def generate_ai_email(max_length, desired_label, max_attempts=3):
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    groq_api_key = os.getenv("GROQ_API_KEY")

    if not gemini_api_key and not groq_api_key:
        return None, "Missing GEMINI_API_KEY or GROQ_API_KEY environment variables."

    prompt_parts = [
        "You are generating training data for a phishing awareness quiz.",
        "Generate one realistic email or message that a real person would receive",
        "in a workplace or personal inbox.",
        "Rules:",
        "- If label is 'phishing': Include at least one subtle red flag",
        "(urgency, spoofed domain, credential request, authority impersonation,",
        "emotional manipulation, or too-good-to-be-true offer).",
        "Use realistic-looking but clearly fake domains. Do NOT use 'example.com'.",
        "- If label is 'legitimate': Write a genuinely safe internal or business email",
        "with no suspicious elements. Reference plausible internal systems,",
        "named colleagues, or specific dates. Do NOT ask for credentials or passwords.",
        "- Format: 3-6 sentences. Include a subject line for roughly half of messages.",
        "If you include a subject line, separate it from the body with a double newline (\\n\\n).",
        "- Vary the sender persona: IT, HR, Finance, Manager, External vendor,",
        "Shipping company, Bank, Social media platform, etc.",
        f"- The label must be exactly '{desired_label}'.",
        "- Return ONLY a JSON object with keys 'text' and 'label'.",
        "No markdown, no extra keys, no explanation.",
    ]
    prompt = " ".join(prompt_parts)

    # 1. Try Gemini
    if genai and gemini_api_key:
        client = genai.Client(api_key=gemini_api_key)
        for _attempt in range(max_attempts):
            try:
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7,
                    ),
                )
                raw_text = response.text
                match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                if match:
                    email = json.loads(match.group(0))
                    text = email.get("text", "").strip()
                    label = email.get("label", "").strip().lower()
                    if text and label == desired_label and len(text) <= max_length:
                        return {"text": text, "label": label}, None
            except Exception as e:
                print(f"Gemini generation failed: {e}")
                break  # Fall back to Groq if Gemini fails completely

    # 2. Try Groq Fallback
    if Groq and groq_api_key:
        client = Groq(api_key=groq_api_key)
        for _attempt in range(max_attempts):
            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_completion_tokens=256,
                    top_p=1,
                    stream=False,
                )
                raw_text = completion.choices[0].message.content if completion.choices else ""
                match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                if match:
                    email = json.loads(match.group(0))
                    text = email.get("text", "").strip()
                    label = email.get("label", "").strip().lower()
                    if text and label == desired_label and len(text) <= max_length:
                        return {"text": text, "label": label}, None
            except Exception as exc:
                return None, f"AI service error (Groq fallback): {exc}"

    return None, "AI response did not meet requirements after all attempts."


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.getenv("PHISHGUARD_DATA_PATH", os.path.join(current_dir, "phishing_data.json"))
    feedback_dir = os.getenv("PHISHGUARD_FEEDBACK_DIR", os.path.join(current_dir, "FeedBack"))
    max_feedback_length = int(os.getenv("PHISHGUARD_MAX_FEEDBACK", DEFAULT_MAX_FEEDBACK_LENGTH))
    max_email_length = int(os.getenv("PHISHGUARD_MAX_EMAIL", DEFAULT_MAX_EMAIL_LENGTH))
    max_dataset_size = int(os.getenv("PHISHGUARD_MAX_DATASET", DEFAULT_MAX_DATASET_SIZE))
    min_feedback_interval = float(
        os.getenv("PHISHGUARD_MIN_FEEDBACK_INTERVAL", DEFAULT_MIN_FEEDBACK_INTERVAL)
    )

    emails = load_emails(data_path)
    email_lock = threading.Lock()
    recent_requests = {}

    def is_rate_limited(key, interval_seconds):
        now = time.time()
        last = recent_requests.get(key, 0)
        if now - last < interval_seconds:
            return True
        recent_requests[key] = now
        return False

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health_check():
        return jsonify({"status": "ok"})

    @app.get("/get-email")
    def get_email():
        desired_label = random.choice(["phishing", "legitimate"])
        email = None
        last_error = None
        for _attempt in range(2):
            email, last_error = generate_ai_email(max_email_length, desired_label)
            if email:
                break
            time.sleep(0.4)
        if not email:
            if emails:
                return jsonify(random.choice(emails))
            return json_error(last_error or "AI service error.", 503)
        with email_lock:
            if len(emails) >= max_dataset_size:
                return json_error("Dataset limit reached. Please try later.", 429)
            emails.append(email)
            save_emails(data_path, emails)
        return jsonify(email)

    @app.post("/submit-feedback")
    def submit_feedback():
        requester = request.remote_addr or "unknown"
        if is_rate_limited(f"feedback:{requester}", min_feedback_interval):
            return json_error("Please wait before submitting more feedback.", 429)
        payload = request.get_json(silent=True) or {}
        feedback_text = str(payload.get("feedback", "")).strip()
        if not feedback_text:
            return json_error("Feedback text is required.", 400)
        if len(feedback_text) > max_feedback_length:
            return json_error("Feedback is too long.", 400)

        os.makedirs(feedback_dir, exist_ok=True)
        timestamp = int(time.time())
        feedback_file_path = os.path.join(feedback_dir, f"feedback_{timestamp}.json")
        with open(feedback_file_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "feedback": feedback_text,
                    "created_at": timestamp,
                    "user_agent": request.headers.get("User-Agent", ""),
                },
                handle,
                indent=2,
                ensure_ascii=False,
            )
        return jsonify({"message": "Feedback submitted successfully!"})

    return app


app = create_app()


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    host = os.getenv("PHISHGUARD_HOST", "127.0.0.1")
    port = int(os.getenv("PHISHGUARD_PORT", "5000"))
    try:
        app.run(host=host, port=port, debug=debug)
    except Exception as exc:
        print(f"Failed to start the server: {exc}")
