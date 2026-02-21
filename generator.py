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
Write a professional, cinematic screenplay (exactly 5 to 6 scenes).
- IMPORTANT: Number every scene clearly (e.g., SCENE 1: INT. LOCATION - DAY).
- Focus on logical flow, character development, and narrative depth.
- Create vivid, evocative action lines that describe the atmosphere and character beats.
- Write meaningful, extended dialogue that reflects the characters' status and emotions.
- Avoid meta-labels like "**Action:**" — let the screenplay formatting speak for itself.

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
def parse_response(raw: str) -> dict:
    """
    Split the raw model response into three sections using robust regex.
    """
    keywords = {
        "screenplay": "SCREENPLAY",
        "characters": "CHARACTERS",
        "sound": "SOUND_DESIGN",
        "end": "END"
    }

    def find_section_start(key):
        kw = keywords[key]
        # 1. Strict: === KEY ===
        pattern_strict = r"(?:\*\*|__)?\s*={2,}\s*" + re.escape(kw) + r"\s*={2,}\s*(?:\*\*|__)?"
        match = re.search(pattern_strict, raw, re.IGNORECASE)
        if match: return match
        
        # 2. Markdown Header: ### KEY
        pattern_md = r"(?:\*\*|__)?\s*#{1,6}\s*" + re.escape(kw) + r"\s*(?:\*\*|__)?"
        match_md = re.search(pattern_md, raw, re.IGNORECASE)
        if match_md: return match_md

        # 3. Bold/Standalone: **KEY** or just KEY on a line
        pattern_loose = r"(?:^|\n)\s*(?:\*\*|__)?\s*" + re.escape(kw) + r"\s*(?:\*\*|__)?\s*(?:$|\n)"
        match_loose = re.search(pattern_loose, raw, re.IGNORECASE | re.MULTILINE)
        if match_loose: return match_loose

        return None

    # Find positions
    sp_match = find_section_start("screenplay")
    ch_match = find_section_start("characters")
    sd_match = find_section_start("sound")
    end_match = find_section_start("end")

    def extract(start_match, end_match_candidate):
        if not start_match: return ""
        start_idx = start_match.end()
        end_idx = end_match_candidate.start() if end_match_candidate else len(raw)
        return raw[start_idx:end_idx].strip()

    screenplay = ""
    characters = ""
    sound = ""

    if not (sp_match or ch_match or sd_match):
        logger.warning("No section markers found. Falling back to thirds split.")
        L = len(raw)
        screenplay = raw[:L//3].strip()
        characters = raw[L//3 : 2*L//3].strip()
        sound = raw[2*L//3:].strip()
    else:
        # Screenplay mapping
        sp_end = sp_match.end() if sp_match else 0
        all_stops = [m for m in [ch_match, sd_match, end_match] if m and m.start() >= sp_end]
        next_after_sp = min(all_stops, key=lambda m: m.start()) if all_stops else None
        screenplay = extract(sp_match, next_after_sp)

        # Characters mapping
        if ch_match:
            ch_end = ch_match.end()
            all_stops_ch = [m for m in [sd_match, end_match] if m and m.start() >= ch_end]
            next_after_ch = min(all_stops_ch, key=lambda m: m.start()) if all_stops_ch else None
            characters = extract(ch_match, next_after_ch)
            
        # Sound mapping
        if sd_match:
            sd_end = sd_match.end()
            all_stops_sd = [m for m in [end_match] if m and m.start() >= sd_end]
            next_after_sd = min(all_stops_sd, key=lambda m: m.start()) if all_stops_sd else None
            sound = extract(sd_match, next_after_sd)

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
