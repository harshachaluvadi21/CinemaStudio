# 🎬 Cinema Studio

> **AI-Powered Storyboard & Script Generator** — runs entirely offline using IBM's Granite4 Micro model via Ollama.

---

## Features

- **Simple Access** — No registration required; just enter your name to start
- **AI Story Pipeline** — Enter a story concept → get a full screenplay, character profiles, and sound design notes
- **Export** — Download any section as **TXT**, **PDF**, or **DOCX**
- **100% Offline** — All AI inference runs locally via Ollama; no external APIs at runtime

---

## Requirements

| Tool | Version |
|------|---------|
| Python | 3.8+ |
| Ollama | Latest |
| Granite4 Micro model | via `ollama pull` |

---

## Setup

### 1. Install Ollama

Download from [https://ollama.com](https://ollama.com) and install for your OS.

### 2. Pull the Granite4 Micro model

```bash
ollama pull granite4:micro
```

### 3. Start the Ollama server

```bash
ollama serve
```

> Ollama runs on `http://localhost:11434` by default.

### 4. Clone / navigate to the project

```bash
cd /path/to/cofmov
```

### 5. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate       # macOS/Linux
# venv\Scripts\activate        # Windows

pip install -r requirements.txt
```

### 6. Run the app

```bash
python app.py
```

Open your browser at **http://127.0.0.1:5000**

---

## Usage

1. **Enter Name** on the Landing Page
2. On the **Dashboard**, enter your story concept (up to 2000 characters)
3. Click **Generate Script** — the AI will produce:
   - 📜 A formatted screenplay (INT./EXT. headings, dialogue)
   - 🎭 Character profiles (~150 words each, psychological depth)
   - 🎵 Scene-by-scene sound design notes
4. **Export** any section as TXT, PDF, or DOCX using the buttons in each section

---

## Project Structure

```
cofmov/
├── app.py           # Flask app factory, routes
├── generator.py     # Ollama API integration & prompt builder
├── export.py        # TXT / PDF / DOCX generation
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── landing.html
│   └── dashboard.html
├── static/
│   ├── css/style.css
│   └── js/main.js
└── tests/
    ├── conftest.py
    └── test_generator.py
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use an in-memory SQLite database and mock the Ollama API — no Ollama server needed for testing.

---

## Security Notes

- Passwords are **never stored in plaintext** (Werkzeug PBKDF2-SHA256 hashing)
- All SQL queries use **parameterized statements** (no string formatting)
- **CSRF tokens** on every form (Flask-WTF)
- Session cookies are **HttpOnly** by default; set `SESSION_COOKIE_SECURE=True` in production (HTTPS)
- Generated content is **not persisted** to disk — held in session memory only

---

## Configuration

Set the `SECRET_KEY` environment variable in production:

```bash
export SECRET_KEY="your-very-long-random-secret-key"
python app.py
```

---

## License

MIT
