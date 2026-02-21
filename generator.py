"""
generator.py — Ollama/Granite4 Micro integration for Coffee-with-Cinema.

Builds a structured prompt requesting a screenplay, character profiles, and
sound design notes. Calls the local Ollama API with retry/backoff logic and
parses the three sections from the response.
"""

import time
import logging
import requests
import re

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


def build_prompt(storyline: str, genre: str = "Cinematic Default", character_names: str = "") -> str:
    """
    Construct a professional screenplay prompt with clear section markers.
    """
    char_instruction = f"\nPrimary Cast: {character_names}\nUse these specific character names and roles in your generation." if character_names else ""

    return f"""You are an elite screenwriter and story architect specializing in {genre} cinema, with deep expertise in Indian/Telugu (Tollywood) storytelling.

Story Concept: {storyline}
Genre/Style: {genre}{char_instruction}

Task: Produce a comprehensive screenplay, deep character profiles, and a complete scene-by-scene sound guide. Use Indian/Telugu names and cultural nuances naturally.

{SECTION_MARKERS['screenplay']}
Write a comprehensive, professional screenplay (exactly 6 EXTENDED, DENSE scenes) with proper formatting.
IMPORTANT: Number every scene header (e.g., "SCENE 1: INT. HOUSE - DAY").
- Focus on CRYSTAL CLEAR VISUALIZATION and LOGICAL FLOW.
- Do not rush. Develop each scene fully.
- Character names centered above dialogue (Use Indian names like Arjun, Priya, Rao, etc.)
- EXTREME DETAIL in Action lines: Describe the setting, atmosphere, micro-expressions, and props in depth.
- Extended Dialogue: Write long, meaningful conversations. Include "punch dialogues" and emotional monologues.

{SECTION_MARKERS['characters']}
Provide detailed character profiles for the main cast (2–3 characters).
### [NAME]
- Age: [Age]
- Persona: Deep dive into their background, personality, and motivations.
- Arc: Their journey through this story.

{SECTION_MARKERS['sound']}
Write the COMPREHENSIVE sound design guide.
IMPORTANT: You MUST provide a sound design entry for EVERY SINGLE SCENE generated in the screenplay above. Do not skip any scene numbers.
Format:
SCENE 1: [Slugline]
- Ambient: Detailed background soundscapes.
- FX: Specific sound effects for key actions.
- Music: Thematic score or musical atmosphere.

SCENE 2: [Slugline]
... (and so on for ALL 5-6 scenes).

{SECTION_MARKERS['end']}
"""


def parse_response(raw: str) -> dict:
    """
    Split the raw model response into three sections using robust regex.

    Args:
        raw: The full text returned by the model.

    Returns:
        Dict with keys 'screenplay', 'characters', 'sound'.
    """
    m = SECTION_MARKERS
    
    # Matches markers with optional surrounding whitespace/formatting
    def search_marker(marker):
        clean_marker = re.escape(marker).replace(r'\ ', r'\s*')
        pattern = r"(?:\*\*|__)?\s*" + clean_marker + r"\s*(?:\*\*|__)?"
        return re.search(pattern, raw, re.IGNORECASE)

    # Find positions of all markers
    sp_match = search_marker(m["screenplay"])
    ch_match = search_marker(m["characters"])
    sd_match = search_marker(m["sound"])
    end_match = search_marker(m["end"])

    def extract(start_match, end_match_candidate):
        if not start_match: return ""
        start_idx = start_match.end()
        end_idx = end_match_candidate.start() if end_match_candidate else len(raw)
        return raw[start_idx:end_idx].strip()

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
        "screenplay": screenplay or "(No screenplay generated. Try again.)",
        "characters": characters or "(No character profiles generated.)",
        "sound": sound or "(No sound design notes generated.)",
    }


def generate_content(storyline: str, genre: str = "Cinematic Default", character_names: str = "") -> dict:
    """
    Call the local Ollama API and return parsed screenplay, characters, sound.

    Retries up to MAX_RETRIES times with exponential backoff on failure.

    Args:
        storyline: The user's story concept.
        genre: The requested genre/tone.
        character_names: Preferred names for the cast.

    Returns:
        Dict with keys 'screenplay', 'characters', 'sound'.

    Raises:
        RuntimeError: If the Ollama server is unreachable after all retries.
    """
    prompt = build_prompt(storyline, genre, character_names)
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
