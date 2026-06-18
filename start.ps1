# PhishGuard - Dev Server Startup Script
# Usage: .\start.ps1
# Set your API keys here (or export them from your system environment)

# ── Required: At least one of these must be set ──────────────────────────────
$env:GEMINI_API_KEY = "your_gemini_key_here"
$env:GROQ_API_KEY   = "your_groq_key_here"

# ── Start the server ─────────────────────────────────────────────────────────
Write-Host "Starting PhishGuard..." -ForegroundColor Cyan
Write-Host "GEMINI_API_KEY set: $($env:GEMINI_API_KEY -ne $null -and $env:GEMINI_API_KEY -ne '')" -ForegroundColor Gray
Write-Host "GROQ_API_KEY   set: $($env:GROQ_API_KEY   -ne $null -and $env:GROQ_API_KEY   -ne '')" -ForegroundColor Gray
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe app.py
