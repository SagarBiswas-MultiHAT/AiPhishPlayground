# PhishGuard - Dev Server Startup Script
# Usage: .\start.ps1
# Set your API keys here (or export them from your system environment)

# ── Required: At least one of these must be set ──────────────────────────────
# Keys set in the terminal BEFORE running this script take priority.
# Only fill in the quotes below if you want the script to manage your keys.
if (-not $env:GEMINI_API_KEY)   { $env:GEMINI_API_KEY   = "your_gemini_key_here" }
if (-not $env:GROQ_API_KEY)     { $env:GROQ_API_KEY     = "your_groq_key_here" }

# ── Optional: DeepSeek API (fallback when Gemini/Llama quota exhausted) ───────
if (-not $env:DEEPSEEK_API_KEY) { $env:DEEPSEEK_API_KEY = "your_deepseek_key_here" }

# ── Start the server ─────────────────────────────────────────────────────────
Write-Host "Starting PhishGuard..." -ForegroundColor Cyan
Write-Host "GEMINI_API_KEY   set: $($env:GEMINI_API_KEY   -ne $null -and $env:GEMINI_API_KEY   -ne '' -and $env:GEMINI_API_KEY   -ne 'your_gemini_key_here')" -ForegroundColor Gray
Write-Host "GROQ_API_KEY     set: $($env:GROQ_API_KEY     -ne $null -and $env:GROQ_API_KEY     -ne '' -and $env:GROQ_API_KEY     -ne 'your_groq_key_here')" -ForegroundColor Gray
Write-Host "DEEPSEEK_API_KEY set: $($env:DEEPSEEK_API_KEY -ne $null -and $env:DEEPSEEK_API_KEY -ne '' -and $env:DEEPSEEK_API_KEY -ne 'your_deepseek_key_here')" -ForegroundColor Gray
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe app.py
