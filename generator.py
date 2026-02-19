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
- DO NOT INCLUDE CHARACTER PROFILES OR SOUND DESIGN IN THIS SECTION.

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
def parse_response(raw: str) -> dict:
    """
    Split the raw model response into three sections using robust regex.

    Args:
        raw: The full text returned by the model.

    Returns:
        Dict with keys 'screenplay', 'characters', 'sound'.
    """
    # keywords mapped to keys
    keywords = {
        "screenplay": "SCREENPLAY",
        "characters": "CHARACTERS",
        "sound": "SOUND_DESIGN",
        "end": "END"
    }

    def find_section_start(key):
        kw = keywords[key]
        # 1. Strict: === KEY === (with optional spaces/bold)
        pattern_strict = r"(?:\*\*|__)?\s*={2,}\s*" + re.escape(kw) + r"\s*={2,}\s*(?:\*\*|__)?"
        match = re.search(pattern_strict, raw, re.IGNORECASE)
        if match:
            return match
        
        # 2. Markdown Header: ### KEY
        pattern_md = r"(?:\*\*|__)?\s*#{1,6}\s*" + re.escape(kw) + r"\s*(?:\*\*|__)?"
        match_md = re.search(pattern_md, raw, re.IGNORECASE)
        if match_md:
            return match_md

        # 3. Bold/Standalone: **KEY** or just KEY on a line
        # We need to be careful not to match "Key" inside a sentence.
        # Enforce start of line or newline, and end of line.
        pattern_loose = r"(?:^|\n)\s*(?:\*\*|__)?\s*" + re.escape(kw) + r"\s*(?:\*\*|__)?\s*(?:$|\n)"
        match_loose = re.search(pattern_loose, raw, re.IGNORECASE | re.MULTILINE)
        if match_loose:
            return match_loose

        return None

    # Find positions
    sp_match = find_section_start("screenplay")
    ch_match = find_section_start("characters")
    sd_match = find_section_start("sound")
    end_match = find_section_start("end")

    # Helper to extract text between two optional match objects
    def extract(start_match, end_match_candidate):
        if not start_match:
            return ""
        start_idx = start_match.end()
        end_idx = end_match_candidate.start() if end_match_candidate else len(raw)
        return raw[start_idx:end_idx].strip()

    screenplay = ""
    characters = ""
    sound = ""

    # If absolutely no markers found, use thirds as last resort hail mary
    if not (sp_match or ch_match or sd_match):
        logger.warning("No section markers found. Falling back to thirds split.")
        L = len(raw)
        screenplay = raw[:L//3].strip()
        characters = raw[L//3 : 2*L//3].strip()
        sound = raw[2*L//3:].strip()
    else:
        # Determine strict order boundaries
        # We need to find the "next" section start for each section
        
        # For Screenplay: start at sp_match, end at ch_match OR sd_match OR end_match
        # But what if ch_match is missing? 
        # We need to find the earliest match that appears AFTER sp_match
        
        matches = []
        if ch_match: matches.append(ch_match)
        if sd_match: matches.append(sd_match)
        if end_match: matches.append(end_match)
        
        # Filter matches that are actually after sp_match (if it exists)
        sp_end = sp_match.end() if sp_match else 0
        valid_next_matches = [m for m in matches if m.start() >= sp_end]
        next_after_sp = min(valid_next_matches, key=lambda m: m.start()) if valid_next_matches else None
        
        screenplay = extract(sp_match, next_after_sp)

        # For Characters: start at ch_match
        if ch_match:
            ch_end = ch_match.end()
            matches_after_ch = []
            if sd_match: matches_after_ch.append(sd_match)
            if end_match: matches_after_ch.append(end_match)
            
            valid_next = [m for m in matches_after_ch if m.start() >= ch_end]
            next_after_ch = min(valid_next, key=lambda m: m.start()) if valid_next else None
            characters = extract(ch_match, next_after_ch)
            
        # For Sound: start at sd_match
        if sd_match:
            sd_end = sd_match.end()
            matches_after_sd = []
            if end_match: matches_after_sd.append(end_match)
            
            valid_next = [m for m in matches_after_sd if m.start() >= sd_end]
            next_after_sd = min(valid_next, key=lambda m: m.start()) if valid_next else None
            sound = extract(sd_match, next_after_sd)

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
