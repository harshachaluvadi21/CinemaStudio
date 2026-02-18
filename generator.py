"""
generator.py — Ollama/Granite4 Micro integration for Coffee-with-Cinema.

Builds a structured prompt requesting a screenplay, character profiles, and
sound design notes. Calls the local Ollama API with retry/backoff logic and
parses the three sections from the response.
"""

import time
import logging
import requests

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "granite4:micro"
TEMPERATURE = 0.7
MAX_RETRIES = 5

SECTION_MARKERS = {
    "screenplay": "===SCREENPLAY===",
    "characters": "===CHARACTERS===",
    "sound": "===SOUND_DESIGN===",
    "end": "===END===",
}


def build_prompt(storyline: str) -> str:
    """
    Construct the structured prompt sent to the Granite4 Micro model.

    The prompt instructs the model to produce three clearly delimited sections
    so they can be reliably parsed from the response.

    Args:
        storyline: The user's story concept (plain text).

    Returns:
        A formatted prompt string.
    """
    return f"""You are a professional screenwriter, character analyst, and sound designer.
Based on the following story concept, produce three sections in order.
Use EXACTLY the section markers shown below — do not add extra text before or after them.

Story concept: {storyline}

IMPORTANT: DO NOT output any introductory text (like "Here is the screenplay"). Output ONLY the requested sections.

{SECTION_MARKERS['screenplay']}
Write a professional screenplay (3–5 scenes) with proper formatting:
- Scene headings in ALL CAPS (ex: INT. ROOM - NIGHT)
- Character names centered above dialogue
- Action lines in sentence case describing what we see
- Dialogue in standard screenplay format with proper spacing

{SECTION_MARKERS['characters']}
Write detailed character profiles (~150 words each) for the 2–3 main characters.
For each character include:
- Name and Age
- Background and Personality
- Psychological depth
- Motivations
- Character arc

{SECTION_MARKERS['sound']}
Write a scene-by-scene sound design guide.
For each scene list:
- Ambient sounds
- Sound effects (Foley)
- Background music suggestions
- Mixing notes
- Mood based recommendations
Format each scene with its heading (e.g. Scene 1: INT. BARN - NIGHT).

{SECTION_MARKERS['end']}
"""


def _extract_section(text: str, start_marker: str, end_marker: str) -> str:
    """Extract text between two markers, stripping whitespace."""
    try:
        start = text.index(start_marker) + len(start_marker)
        end = text.index(end_marker, start)
        return text[start:end].strip()
    except ValueError:
        return ""


def parse_response(raw: str) -> dict:
    """
    Split the raw model response into three sections.

    Falls back to splitting the text into thirds if markers are missing
    (e.g. the model ignored the format instructions).

    Args:
        raw: The full text returned by the model.

    Returns:
        Dict with keys 'screenplay', 'characters', 'sound'.
    """
    m = SECTION_MARKERS
    # Check if any section markers are present at all
    markers_present = m["screenplay"] in raw and m["characters"] in raw and m["sound"] in raw and m["end"] in raw

    if not markers_present:
        # Fallback: markers were not respected — split into thirds
        logger.warning("Section markers not found; falling back to thirds split.")
        third = max(len(raw) // 3, 1)
        screenplay = raw[:third].strip()
        characters = raw[third : 2 * third].strip()
        sound = raw[2 * third :].strip()
    else:
        screenplay = _extract_section(raw, m["screenplay"], m["characters"])
        characters = _extract_section(raw, m["characters"], m["sound"])
        sound = _extract_section(raw, m["sound"], m["end"])

    return {
        "screenplay": screenplay or "(No screenplay generated.)",
        "characters": characters or "(No character profiles generated.)",
        "sound": sound or "(No sound design notes generated.)",
    }


def generate_content(storyline: str) -> dict:
    """
    Call the local Ollama API and return parsed screenplay, characters, sound.

    Retries up to MAX_RETRIES times with exponential backoff on failure.

    Args:
        storyline: The user's story concept.

    Returns:
        Dict with keys 'screenplay', 'characters', 'sound'.

    Raises:
        RuntimeError: If the Ollama server is unreachable after all retries.
    """
    prompt = build_prompt(storyline)
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": 3000,
        },
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            logger.info("Ollama request attempt %d/%d", attempt + 1, MAX_RETRIES)
            resp = requests.post(OLLAMA_URL, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data.get("response", "")
            return parse_response(raw_text)
        except requests.RequestException as exc:
            last_error = exc
            wait = 2 ** attempt
            logger.warning(
                "Ollama request failed (attempt %d): %s. Retrying in %ds…",
                attempt + 1,
                exc,
                wait,
            )
            time.sleep(wait)

    raise RuntimeError(
        f"Ollama server at {OLLAMA_URL} did not respond after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )
