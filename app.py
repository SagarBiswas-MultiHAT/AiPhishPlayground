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
DEFAULT_MAX_EMAIL_LENGTH = 800  # Raised from 600 - Gemini 2.5-flash outputs ~650 chars
DEFAULT_MIN_FEEDBACK_INTERVAL = 2.0

# ─── Consensus Engine Constants ─────────────────────────────────────────────
# Maximum number of rounds the two models are allowed to disagree before we
# give up and fall back to the static dataset.  Each round = 1 Gemini call +
# 1 Groq/Llama call, so keep this reasonable to avoid runaway API spend.
MAX_CONSENSUS_ROUNDS = 5

# ─── Gemini Model Waterfall ──────────────────────────────────────────────────
# Models are tried in order.  When a 429 / quota error is detected the engine
# immediately moves to the next entry instead of wasting retries.
GEMINI_MODELS = [
    "gemini-2.0-flash",   # Primary  - best quality
    "gemini-2.5-flash",   # Fallback - separate free-tier quota bucket
    "gemini-3.5-flash",   # Fallback 2
]

# ─── Prefetch Cache ──────────────────────────────────────────────────────────
# One email is pre-generated in the background while the user is reading the
# current question.  When the next /get-email request arrives the cached email
# is returned instantly, then a new background generation begins immediately.
_prefetch_lock  = threading.Lock()
_prefetch_cache = None   # pre-generated email dict, or None
_prefetch_busy  = False  # True while a background thread is active


def _run_prefetch(max_length):
    """Background worker: silently generate the next email and fill the cache."""
    global _prefetch_cache, _prefetch_busy
    try:
        label = random.choice(["phishing", "legitimate"])
        print(f"[Prefetch] Background generation started (label={label!r})...")
        email, _ = generate_ai_email(max_length, label)
        with _prefetch_lock:
            _prefetch_cache = email
        if email:
            print(f"[Prefetch] Cache ready (label={email.get('label')!r}).")
        else:
            print("[Prefetch] Background generation failed - cache remains empty.")
    except Exception as exc:
        print(f"[Prefetch] Background error: {exc}")
    finally:
        with _prefetch_lock:
            _prefetch_busy = False


def _trigger_prefetch(max_length):
    """Spawn a background prefetch thread if one is not already running."""
    global _prefetch_busy
    with _prefetch_lock:
        if _prefetch_busy:
            return  # already warming - don't double-fetch
        _prefetch_busy = True
    threading.Thread(
        target=_run_prefetch,
        args=(max_length,),
        daemon=True,
        name="phishguard-prefetch",
    ).start()


def _pop_prefetch_cache():
    """Thread-safely consume and return the cached email (or None if empty)."""
    global _prefetch_cache
    with _prefetch_lock:
        email = _prefetch_cache
        _prefetch_cache = None
    return email

# Prompt shared by both generation and classification phases
_GENERATION_PROMPT_PARTS = [
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
    "- Return ONLY a JSON object with keys 'text' and 'label'.",
    "No markdown, no extra keys, no explanation.",
]


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


# ─── Step 1: Gemini generates the question (email) + its own answer (label) ──
def _is_quota_error(exc):
    """Return True if the exception is a 429 / quota-exhausted error."""
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()


def _is_auth_error(exc):
    """Return True if the exception is a 401 auth error (bad/expired key)."""
    msg = str(exc)
    return "401" in msg or "UNAUTHENTICATED" in msg or "API_KEY_INVALID" in msg


class _GeminiAuthFailed(Exception):
    """Raised to immediately abort all Gemini consensus rounds on auth failure."""
    pass


def _gemini_generate(client, desired_label, max_length):
    """Ask Gemini to generate a phishing/legitimate email with its label.

    Tries each model in GEMINI_MODELS in order.  A 429 / quota error causes
    an immediate skip to the next model; other errors are retried once.

    Returns (email_dict, None) on success or (None, error_str) on failure.
    email_dict has the shape {"text": str, "label": str, "_model": str}.
    """
    prompt_parts = _GENERATION_PROMPT_PARTS + [
        f"- The label must be exactly '{desired_label}'.",
    ]
    prompt = " ".join(prompt_parts)

    last_error = "No Gemini models available."

    for model_name in GEMINI_MODELS:
        print(f"[Gemini] Trying model: {model_name}")
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                ),
            )
            raw_text = response.text or ""
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if not match:
                last_error = f"{model_name}: returned no JSON object."
                continue  # try next model
            email = json.loads(match.group(0))
            text = email.get("text", "").strip()
            label = email.get("label", "").strip().lower()
            if text and label == desired_label and len(text) <= max_length:
                print(f"[Gemini] Success with {model_name}")
                return {"text": text, "label": label, "_model": model_name}, None
            last_error = f"{model_name}: output failed validation (label={label!r}, len={len(text)})."
            # Validation failure is not a quota issue — no point trying the next model
            # for the same prompt; break and let the caller retry the whole round.
            break
        except Exception as exc:
            if _is_auth_error(exc):
                print(f"[Gemini] FATAL: {model_name} auth failed (bad API key) - aborting all Gemini calls.")
                raise _GeminiAuthFailed(str(exc))
            if _is_quota_error(exc):
                print(f"[Gemini] {model_name} quota exhausted - trying next model.")
                last_error = f"{model_name}: quota exhausted."
                continue  # immediately skip to next model
            print(f"[Gemini] {model_name} error: {exc}")
            last_error = f"{model_name}: {exc}"
            break  # non-quota error - stop trying Gemini models

    return None, last_error


# ─── Step 2: Llama independently classifies the generated email ──────────────
def _llama_classify(client, email_text):
    """Ask Llama-3.3-70b-versatile to classify an email as phishing or legitimate.

    Critically, we do NOT reveal the label Gemini assigned — Llama must decide
    on its own.  This enforces true independent verification.

    Returns "phishing" | "legitimate" | None (on failure).
    """
    classify_prompt = (
        "You are a cybersecurity expert evaluating an email for a phishing awareness quiz.\n"
        "Read the following email and decide whether it is phishing or legitimate.\n"
        "Reply with exactly ONE word — either 'phishing' or 'legitimate' — and nothing else.\n\n"
        f"Email:\n{email_text}"
    )
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": classify_prompt}],
            temperature=0.2,       # Low temperature for deterministic classification
            max_completion_tokens=5,
            top_p=1,
            stream=False,
        )
        raw = completion.choices[0].message.content.strip().lower() if completion.choices else ""
        # Accept any response that contains one of the two labels
        if "phishing" in raw:
            return "phishing"
        if "legitimate" in raw:
            return "legitimate"
        return None
    except Exception as exc:
        print(f"Llama classification error: {exc}")
        return None


# ─── Consensus Engine ────────────────────────────────────────────────────────
def generate_ai_email(max_length, desired_label, max_attempts=3):
    """Dual-model consensus loop.

    Algorithm
    ---------
    Step 1 - Gemini generates an email and asserts a label.
    Step 2 - Llama-3.3-70b-versatile independently classifies the same email.
    Step 3 - If both labels match  ->  return the email (consensus locked).
              If they differ       ->  repeat from Step 1 (new round).
    After MAX_CONSENSUS_ROUNDS rounds without consensus  ->
        fall back to Llama generating the question directly (no static dataset).
    """
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    groq_api_key = os.getenv("GROQ_API_KEY")

    if not gemini_api_key and not groq_api_key:
        return None, "Missing GEMINI_API_KEY or GROQ_API_KEY environment variables."

    # If only one key is available, skip consensus and generate with whatever is available.
    if not (gemini_api_key and groq_api_key):
        return _single_model_fallback(
            gemini_api_key, groq_api_key, max_length, desired_label, max_attempts
        )

    gemini_client = genai.Client(api_key=gemini_api_key) if genai else None
    groq_client = Groq(api_key=groq_api_key) if Groq else None

    if not gemini_client or not groq_client:
        return _single_model_fallback(
            gemini_api_key, groq_api_key, max_length, desired_label, max_attempts
        )

    last_error = "No consensus reached after all rounds."

    for round_num in range(1, MAX_CONSENSUS_ROUNDS + 1):
        print(f"[Consensus] Round {round_num}/{MAX_CONSENSUS_ROUNDS} - desired label: {desired_label!r}")

        # ── Step 1: Gemini generates question + answer ──────────────────────
        try:
            email, gen_error = _gemini_generate(gemini_client, desired_label, max_length)
        except _GeminiAuthFailed as auth_exc:
            print(f"[Consensus] FATAL: Gemini auth failed - skipping all rounds. Check your GEMINI_API_KEY.")
            last_error = f"Gemini API key is invalid (401). Please set a valid GEMINI_API_KEY."
            break  # exit the consensus loop immediately
        if email is None:
            print(f"[Consensus] Round {round_num}: Gemini generation failed - {gen_error}")
            last_error = gen_error
            continue

        gemini_label = email["label"]
        email_text = email["text"]
        print(f"[Consensus] Round {round_num}: Gemini generated email, label={gemini_label!r}")

        # ── Step 2: Llama independently classifies the email ─────────────────
        llama_label = _llama_classify(groq_client, email_text)
        if llama_label is None:
            print(f"[Consensus] Round {round_num}: Llama classification failed (network/auth error). Falling back to Gemini-only.")
            email["_validated"] = False
            email["_consensus_round"] = 0
            return email, None

        print(f"[Consensus] Round {round_num}: Llama classified as {llama_label!r}")

        # ── Step 3: Check consensus ──────────────────────────────────────────
        if llama_label == gemini_label:
            print(f"[Consensus] Consensus reached on round {round_num} - label={gemini_label!r}")
            email["_validated"] = True
            email["_consensus_round"] = round_num
            return email, None
        else:
            print(
                f"[Consensus] Round {round_num}: Disagreement - "
                f"Gemini={gemini_label!r}, Llama={llama_label!r}. Re-running both."
            )
            last_error = (
                f"Round {round_num}: Gemini={gemini_label!r} vs Llama={llama_label!r}."
            )

    # ── Consensus failed: fall back to Llama generating directly ─────────────
    print(f"[Consensus] No consensus after {MAX_CONSENSUS_ROUNDS} rounds. Llama generating directly.")
    return _llama_generate_fallback(groq_client, max_length, desired_label, max_attempts)


def _llama_generate_fallback(groq_client, max_length, desired_label, max_attempts):
    """Llama-3.3-70b-versatile generates a question directly.

    Used when:
    - Gemini is unavailable (no GEMINI_API_KEY)
    - Consensus was never reached after MAX_CONSENSUS_ROUNDS
    Marked as _validated=False so the frontend shows no badge.
    """
    prompt_parts = _GENERATION_PROMPT_PARTS + [
        f"- The label must be exactly '{desired_label}'.",
    ]
    prompt = " ".join(prompt_parts)

    for _ in range(max_attempts):
        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_completion_tokens=300,
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
                    print(f"[Fallback] Llama generated email directly, label={label!r}")
                    return {"text": text, "label": label, "_validated": False, "_consensus_round": 0}, None
        except Exception as exc:
            print(f"[Fallback] Llama generation error: {exc}")
            break

    return None, "Llama fallback also failed to generate a valid email."


def _single_model_fallback(gemini_api_key, groq_api_key, max_length, desired_label, max_attempts):
    """Used when only one API key is available - Gemini waterfall first, then Llama."""
    # Try Gemini with full model waterfall (2.0-flash -> 2.5-flash -> 3.5-flash)
    if genai and gemini_api_key:
        client = genai.Client(api_key=gemini_api_key)
        for _ in range(max_attempts):
            email, err = _gemini_generate(client, desired_label, max_length)
            if email:
                return {
                    "text": email["text"],
                    "label": email["label"],
                    "_validated": False,
                    "_consensus_round": 0,
                    "_model": email.get("_model", "gemini"),
                }, None
            # If all Gemini models are quota-exhausted, stop retrying
            if err and "quota exhausted" in err:
                print(f"[SingleModel] All Gemini models quota-exhausted. Falling back to Llama.")
                break

    # Fall back to Llama if Gemini unavailable or all quota exhausted
    if Groq and groq_api_key:
        groq_client = Groq(api_key=groq_api_key)
        return _llama_generate_fallback(groq_client, max_length, desired_label, max_attempts)

    return None, "No AI service available. Both Gemini quota is exhausted and no GROQ_API_KEY is set."


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    feedback_dir = os.getenv("PHISHGUARD_FEEDBACK_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "FeedBack"))
    max_feedback_length = int(os.getenv("PHISHGUARD_MAX_FEEDBACK", DEFAULT_MAX_FEEDBACK_LENGTH))
    max_email_length = int(os.getenv("PHISHGUARD_MAX_EMAIL", DEFAULT_MAX_EMAIL_LENGTH))
    min_feedback_interval = float(
        os.getenv("PHISHGUARD_MIN_FEEDBACK_INTERVAL", DEFAULT_MIN_FEEDBACK_INTERVAL)
    )

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
        try:
            # ── Step 1: Try to serve from the prefetch cache (instant) ────────
            email = _pop_prefetch_cache()

            if email:
                print("[Prefetch] Served from cache (instant response).")
            else:
                # ── Step 2: Cache miss — generate synchronously ───────────────
                print("[Prefetch] Cache miss — generating synchronously.")
                desired_label = random.choice(["phishing", "legitimate"])
                email = None
                last_error = None
                for _attempt in range(2):
                    email, last_error = generate_ai_email(max_email_length, desired_label)
                    if email:
                        break
                    time.sleep(0.4)

                if not email:
                    _trigger_prefetch(max_email_length)  # still warm cache for next time
                    return json_error(
                        last_error or "AI service unavailable. Please set GEMINI_API_KEY and GROQ_API_KEY.",
                        503,
                    )

            # ── Step 3: Immediately kick off the NEXT generation in background ─
            _trigger_prefetch(max_email_length)

            return jsonify(email)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return json_error(f"Internal Error: {e}", 500)

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

# Warm the prefetch cache at startup so the very first game request is instant
_trigger_prefetch(DEFAULT_MAX_EMAIL_LENGTH)


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    host = os.getenv("PHISHGUARD_HOST", "127.0.0.1")
    port = int(os.getenv("PHISHGUARD_PORT", "5000"))
    try:
        app.run(host=host, port=port, debug=debug)
    except Exception as exc:
        print(f"Failed to start the server: {exc}")
