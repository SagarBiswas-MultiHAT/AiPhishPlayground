# 🛡️ PhishGuard: Your Personal Phishing Radar Trainer

<div align="right">

[![CI](https://img.shields.io/github/actions/workflow/status/SagarBiswas-MultiHAT/Ai-Phishy-Playground/get-started-with-github-actions.yml?branch=main)](https://github.com/SagarBiswas-MultiHAT/Ai-Phishy-Playground/actions)
&nbsp;
![Tests](https://img.shields.io/badge/tests-pytest-brightgreen)
&nbsp;
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
&nbsp;
![License](https://img.shields.io/github/license/SagarBiswas-MultiHAT/Ai-Phishy-Playground)

</div>

Welcome to **PhishGuard**! This is a fast-paced, interactive web game designed to help anyone train their instincts against email phishing attacks. 

Instead of sitting through boring cybersecurity slideshows, PhishGuard throws you right into the deep end: you are shown realistic, AI-generated emails and you have **10 seconds** to decide if it's a safe message or a dangerous scam.

---

![](https://imgur.com/MttZMLQ.png)

---

## 🌟 What is it?

Phishing is a type of online scam where criminals send fake emails to trick you into clicking malicious links or giving away passwords. It is still the #1 way hackers break into systems today.

**PhishGuard** turns learning how to spot these scams into a quick, repeatable game. By practicing with our tool, you will build a stronger, natural instinct for what looks right and what looks suspicious in your inbox.

## ✨ Key Features

* **Real-time AI Generation:** Every email you see is uniquely generated on the spot by powerful Artificial Intelligence (AI). You'll never see the exact same scam twice!
* **High-Stakes Timer:** You only get 10 seconds to make a call. This trains you to spot red flags quickly. Need a break? Just hit the "Pause Timer" button.
* **Dual-AI Verification:** To make sure the game is always accurate, we use two separate AI brains. One creates the email, and the second one verifies it. You'll see a "Dual-AI Verified" badge when they both agree!
* **Track Your Instincts:** Keep an eye on your live score and attempt tracker to see how your phishing radar improves over time.
* **Beautiful 2050 Cyberpunk Design:** A sleek, futuristic interface featuring dynamic particle networks, smooth animations, and automatic Light/Dark mode support.

## 🎮 How to Play

1. **Read the Message:** An email will appear on your screen.
2. **Beat the Clock:** You have 10 seconds to read it and look for clues (weird urgency, strange requests, or unusual formatting).
3. **Make Your Call:** Click **Phishing** if you think it's a scam, or **Legitimate** if you think it's safe.
4. **Get Instant Feedback:** The screen will glow green if you were right, and shake red if you were tricked!
5. **Keep Going:** A brand new, uniquely generated email will load automatically for the next round.

---

## ⚙️ How to Run PhishGuard on Your Computer

While PhishGuard uses advanced AI under the hood, getting it running on your own computer is surprisingly simple. You just need Python installed, and a free API key (like a password) to talk to the AI.

### 1. What You Need
* **Python**: You need Python installed on your computer. If you don't have it, you can download it from [python.org](https://www.python.org/downloads/).
* **An AI Key**: PhishGuard uses Google's AI (Gemini) to write the emails. You need a free key from [Google AI Studio](https://aistudio.google.com/apikey).

### 2. Simple Setup
Open your computer's terminal (Command Prompt or PowerShell) and run these commands to download the project's requirements:

```powershell
# 1. Create a virtual environment (a safe folder for the project)
python -m venv .venv

# 2. Activate the folder
& ".venv/Scripts/Activate.ps1"

# 3. Install the required files
pip install -r requirements.txt
pip install -r requirements-ai.txt
```

### 3. Start the Game!
We've included a simple startup script to make playing easy. 

1. Open the `start.ps1` file in any text editor (like Notepad).
2. Paste your Google Gemini API key where it says `$env:GEMINI_API_KEY = "your_key_here"`.
3. Save the file.
4. Run the script in your terminal:
```powershell
.\start.ps1
```

Finally, open your favorite web browser and go to: **http://127.0.0.1:5000**

---

## 🧠 Behind the Scenes: The Consensus Engine

For the curious minds, here is how PhishGuard ensures the emails are high quality:
Instead of relying on a single AI, PhishGuard uses a "Consensus Engine." 
1. **The Writer (Google Gemini)** is asked to write either a safe email or a scam email.
2. **The Reviewer (Llama 3)** is then shown the email (without knowing what Gemini was asked to do) and is asked to grade it.
3. If both AI models agree on what the email is, the game serves it to you! If they disagree, the system silently throws it away and generates a new one. 

*Note: If you have a slow network or don't have a second API key setup, PhishGuard is smart enough to automatically fallback to using just Gemini so your game never crashes!*

---

### License
This project is open-source and available under the MIT License. Feel free to use it, learn from it, and modify it!