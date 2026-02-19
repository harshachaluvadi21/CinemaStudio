# 🎬 Cinema Studio
> **The Offline AI Writer's Room** — Where your story stays yours.

**Cinema Studio** is a privacy-first, offline creative suite that turns a simple idea into a Hollywood-ready package. Powered by **Ollama (Granite4 Micro)**, it runs entirely on your local machine—zero cloud fees, zero data leakage.

---

## 🌟 Why Cinema Studio? (Unique Features)

### 1. 🎥 Director Mode (Genre Control)
Don't settle for generic AI output. Force the engine to write in specific styles:
- **Film Noir** (Shadowy, cynical)
- **Cyberpunk** (High-tech, low-life)
- **Horror** (Tense, psychological)
- *And more...*

### 2. 🎧 Table Read (Instant Audio)
Hear your dialogue performed instantly. The built-in **Text-to-Speech Engine** acts as your cast, helping you catch awkward rhythm and pacing before you export.

### 3. 🔒 100% Offline & Private
Your Intellectual Property (IP) never leaves your device. Perfect for:
- Confidential scripts
- Airplane mode writing
- Zero-cost inference

### 4. 💾 Professional Workflow
- **State Management**: Save/Load your entire project (`.json`) to resume work anytime.
- **Industry Exports**: Download formatted **PDFs**, **DOCXs**, and **TXT** files.
- **Cinema Experience**: Enjoy movie trivia and cinematic visuals while the AI works.

---

## 🚀 Quick Start

### 1. Install Ollama
Download from [https://ollama.com](https://ollama.com) and install for your OS.

### 2. Pull the Model
```bash
ollama pull granite4:micro
```

### 3. Start the Server
```bash
ollama serve
```

### 4. Run Cinema Studio
```bash
pip install -r requirements.txt
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

---

## 🛠️ Tech Stack
- **Backend**: Flask (Python)
- **AI Engine**: Ollama (Llama/Granite models)
- **Frontend**: Vanilla JS + CSS3 (No heavy frameworks)
- **Storage**: In-memory session + JSON export

## License
MIT
