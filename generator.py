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


def build_prompt(storyline: str, genre: str = "Cinematic Default") -> str:
    """
    Construct the structured prompt sent to the Granite4 Micro model.

    The prompt instructs the model to produce three clearly delimited sections
    so they can be reliably parsed from the response.

    Args:
        storyline: The user's story concept (plain text).
        genre: The requested genre/tone (e.g., "Horror", "Film Noir").

    Returns:
        A formatted prompt string.
    """
    return f"""You are a professional screenwriter, character analyst, and sound designer specializing in the {genre} style, with a focus on Indian/Telugu cinema (Tollywood) storytelling.
Based on the following story concept, produce three sections in order.
Use EXACTLY the section markers shown below — do not add extra text before or after them.

Story concept: {storyline}
Genre/Style: {genre}. Ensure the screenplay, characters, and sound design strictly reflect this tone. Use Indian/Telugu names and cultural context.

IMPORTANT: DO NOT output any introductory text (like "Here is the screenplay"). Output ONLY the requested sections.

{SECTION_MARKERS['screenplay']}
Write a comprehensive, professional screenplay (exactly 6 EXTENDED, DENSE scenes) with proper formatting.
IMPORTANT: Number every scene header (e.g., "SCENE 1: INT. HOUSE - DAY").
- Focus on CRYSTAL CLEAR VISUALIZATION and LOGICAL FLOW.
- Do not rush. Develop each scene fully.
- Character names centered above dialogue (Use Indian names like Arjun, Priya, Rao, etc.)
- EXTREME DETAIL in Action lines: Describe the setting, atmosphere, micro-expressions, and props in depth.
- Extended Dialogue: Write long, meaningful conversations. Include "punch dialogues" and emotional monologues.

{SECTION_MARKERS['characters']}
Write detailed character profiles (~200 words each) for the 2–3 main characters (Use Indian/Telugu names).
Format exactly like this:
### NAME
Description...

For each character include:
- Name and Age
- Background and Personality (Indian context)
- Psychological depth
- Motivations
- Character arc

{SECTION_MARKERS['sound']}
Write a scene-by-scene sound design guide.
IMPORTANT: You MUST match the scene numbers from the screenplay EXACTLY.
Format:
"SCENE 1: [Slugline]"
- Ambient: [Details]
- FX: [Details]
- Music: [Details]

"SCENE 2: [Slugline]"
... and so on for ALL scenes.

{SECTION_MARKERS['end']}
"""


import re

def parse_response(raw: str) -> dict:
    """
    Split the raw model response into three sections using robust regex.

    Args:
        raw: The full text returned by the model.

    Returns:
        Dict with keys 'screenplay', 'characters', 'sound'.
    """
    m = SECTION_MARKERS
    
    # 1. Clean up regex patterns to be flexible with whitespace
    # Matches "===SCREENPLAY===" with optional surrounding whitespace/formatting
    def search_marker(marker):
        # Escape the marker and allow for whitespace or markdown formatting around it
        # e.g. **===SCREENPLAY===** or === SCREENPLAY ===
        clean_marker = re.escape(marker).replace(r'\ ', r'\s*')
        # Allow optional markdown bold/italic chars or spaces around
        pattern = r"(?:\*\*|__)?\s*" + clean_marker + r"\s*(?:\*\*|__)?"
        return re.search(pattern, raw, re.IGNORECASE)

    # Find positions of all markers
    sp_match = search_marker(m["screenplay"])
    ch_match = search_marker(m["characters"])
    sd_match = search_marker(m["sound"])
    end_match = search_marker(m["end"])

    # Helper to extract text between two optional match objects
    def extract(start_match, end_match_candidate):
        if not start_match:
            return ""
        start_idx = start_match.end()
        end_idx = end_match_candidate.start() if end_match_candidate else len(raw)
        return raw[start_idx:end_idx].strip()

    # Logic: try to find sections based on available markers
    # We assume the order: Screenplay -> Characters -> Sound
    
    screenplay = ""
    characters = ""
    sound = ""

    # If NO markers found at all, fall back to thirds
    if not (sp_match or ch_match or sd_match):
        logger.warning("No section markers found. Falling back to thirds split.")
        L = len(raw)
        screenplay = raw[:L//3].strip()
        characters = raw[L//3 : 2*L//3].strip()
        sound = raw[2*L//3:].strip()
    else:
        # Extract Screenplay: from SP marker to CH marker (or SD, or End, or EOF)
        next_after_sp = ch_match or sd_match or end_match
        screenplay = extract(sp_match, next_after_sp)

        # Extract Characters: from CH marker to SD marker (or End, or EOF)
        next_after_ch = sd_match or end_match
        characters = extract(ch_match, next_after_ch)

        # Extract Sound: from SD marker to End marker (or EOF)
        sound = extract(sd_match, end_match)

    return {
        "screenplay": screenplay or "(No screenplay generated. Try again or check the logs.)",
        "characters": characters or "(No character profiles generated.)",
        "sound": sound or "(No sound design notes generated.)",
    }


def generate_content(storyline: str, genre: str = "Cinematic Default") -> dict:
    """
    Call the local Ollama API and return parsed screenplay, characters, sound.

    Retries up to MAX_RETRIES times with exponential backoff on failure.

    Args:
        storyline: The user's story concept.
        genre: The requested genre/tone.

    Returns:
        Dict with keys 'screenplay', 'characters', 'sound'.

    Raises:
        RuntimeError: If the Ollama server is unreachable after all retries.
    """
    prompt = build_prompt(storyline, genre)
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
            resp = requests.post(OLLAMA_URL, json=payload, timeout=600)
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
