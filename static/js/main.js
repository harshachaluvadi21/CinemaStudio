/**
 * main.js — Client-side logic for Cinema Studio dashboard.
 *
 * Handles: AJAX content generation, section navigation, export triggers,
 * character/sound output formatting, char counter, mobile sidebar toggle.
 */

'use strict';

// ── CSRF helper ──────────────────────────────────────────────────────────────
function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

// ── Section navigation ───────────────────────────────────────────────────────
function showSection(sectionId) {
    document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.sidebar__link').forEach(l => l.classList.remove('sidebar__link--active'));

    const section = document.getElementById(sectionId);
    if (section) section.classList.add('active');

    const navLink = document.getElementById('nav-' + sectionId);
    if (navLink) navLink.classList.add('sidebar__link--active');

    // Close mobile sidebar
    document.getElementById('sidebar')?.classList.remove('open');
}

// Attach sidebar nav links and Landing Page logic
document.addEventListener('DOMContentLoaded', () => {
    // ── Landing Page Logic ──────────────────────────────
    const startBtn = document.getElementById('startBtn');
    const nameModal = document.getElementById('nameModal');
    const nameInput = document.getElementById('userNameInput');
    const continueBtn = document.getElementById('continueBtn');
    const nameError = document.getElementById('nameError');

    if (startBtn && nameModal) {
        startBtn.addEventListener('click', () => {
            nameModal.style.display = 'flex';
            nameInput.focus();
        });

        nameInput.addEventListener('input', () => {
            const val = nameInput.value.trim();
            continueBtn.disabled = val.length === 0;
            nameError.style.display = 'none';
        });

        continueBtn.addEventListener('click', async () => {
            const username = nameInput.value.trim();
            if (!username) return;

            try {
                const resp = await fetch('/set_name', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ username })
                });
                if (resp.ok) {
                    window.location.href = '/dashboard';
                } else {
                    const data = await resp.json();
                    nameError.textContent = data.error || 'Error setting name.';
                    nameError.style.display = 'block';
                }
            } catch (e) {
                nameError.textContent = 'Network error.';
                nameError.style.display = 'block';
            }
        });
    }

    // ── Sidebar Logic ──────────────────────────────────
    document.querySelectorAll('.sidebar__link[data-section]').forEach(link => {
        link.addEventListener('click', e => {
            if (link.classList.contains('disabled')) {
                e.preventDefault();
                e.stopPropagation();
                return;
            }
            e.preventDefault();
            showSection(link.dataset.section);
        });
    });

    // Char counter
    const textarea = document.getElementById('storylineInput');
    const counter = document.getElementById('charCount');
    if (textarea && counter) {
        textarea.addEventListener('input', () => {
            counter.textContent = textarea.value.length;
            counter.style.color = textarea.value.length > 1800 ? '#F87171' : '';
        });
    }

    // Mobile hamburger
    const hamburger = document.getElementById('hamburger');
    const sidebar = document.getElementById('sidebar');
    if (hamburger && sidebar) {
        hamburger.addEventListener('click', () => sidebar.classList.toggle('open'));
        // Close sidebar when clicking outside
        document.addEventListener('click', e => {
            if (sidebar.classList.contains('open') &&
                !sidebar.contains(e.target) &&
                e.target !== hamburger) {
                sidebar.classList.remove('open');
            }
        });
    }

    // Auto-dismiss flash messages after 5s
    setTimeout(() => {
        document.querySelectorAll('.flash').forEach(f => {
            f.style.transition = 'opacity 0.5s';
            f.style.opacity = '0';
            setTimeout(() => f.remove(), 500);
        });
    }, 5000);
});

// ── Content Generation ───────────────────────────────────────────────────────
async function generateContent() {
    const storyline = document.getElementById('storylineInput')?.value?.trim();
    const errorDiv = document.getElementById('generateError');
    const btn = document.getElementById('generateBtn');
    const overlay = document.getElementById('loadingOverlay');

    // Clear previous error
    if (errorDiv) { errorDiv.style.display = 'none'; errorDiv.textContent = ''; }

    if (!storyline) {
        showError('Please enter a story concept before generating.', errorDiv);
        return;
    }
    if (storyline.length > 2000) {
        showError('Story concept must be under 2000 characters.', errorDiv);
        return;
    }

    // UI: loading state
    setGenerating(true, btn, overlay);

    const trivia = [
        "Did you know? The first feature-length animated movie was Snow White (1937).",
        "Fun Fact: The sound of the T-Rex in Jurassic Park was a mix of a baby elephant, a tiger, and an alligator.",
        "Cinema History: The first movie ever made was the Roundhay Garden Scene (1888).",
        "Effect Magic: The chocolate river in Willy Wonka was made of real chocolate, water, and cream.",
        "Behind the Scenes: Titanic was the first film to be released on video while still in theaters.",
    ];
    let triviaIdx = 0;
    const spinnerSpan = btn.querySelector('.btn-spinner');
    const originalText = spinnerSpan.innerHTML;

    const triviaInterval = setInterval(() => {
        spinnerSpan.innerHTML = `<span class="spinner spinner--sm"></span> ${trivia[triviaIdx]}`;
        triviaIdx = (triviaIdx + 1) % trivia.length;
    }, 5000);

    try {
        const resp = await fetch('/generate_content', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({ storyline }),
        });

        const data = await resp.json();

        if (!resp.ok || data.error) {
            throw new Error(data.error || 'Generation failed. Please try again.');
        }

        // Populate outputs
        populateScreenplay(data.screenplay || '');
        populateCharacters(data.characters || '');
        populateSound(data.sound || '');

        // Enable sidebar links
        document.querySelectorAll('.sidebar__link.disabled').forEach(link => {
            link.classList.remove('disabled');
        });

        // Show results nav and switch to screenplay
        const resultsNav = document.getElementById('resultsNav');
        if (resultsNav) resultsNav.style.display = 'flex';
        showSection('screenplay');

    } catch (err) {
        showError(err.message || 'An unexpected error occurred.', errorDiv);
        showSection('story-input');
    } finally {
        if (triviaInterval) clearInterval(triviaInterval);
        spinnerSpan.innerHTML = originalText;
        setGenerating(false, btn, overlay);
    }
}

function setGenerating(loading, btn, overlay) {
    if (btn) {
        btn.disabled = loading;
        const text = btn.querySelector('.btn-text');
        const spinner = btn.querySelector('.btn-spinner');
        if (text) text.style.display = loading ? 'none' : 'inline';
        if (spinner) spinner.style.display = loading ? 'inline' : 'none';
    }
    if (overlay) overlay.style.display = loading ? 'flex' : 'none';
}

function showError(msg, container) {
    if (!container) { alert(msg); return; }
    container.textContent = msg;
    container.style.display = 'block';
}

// ── Output Populators ────────────────────────────────────────────────────────

function populateScreenplay(text) {
    const placeholder = document.getElementById('screenplay-placeholder');
    const output = document.getElementById('screenplay-output');
    if (!output) return;

    output.textContent = text;
    if (placeholder) placeholder.style.display = 'none';
    output.style.display = 'block';
}

/**
 * Parse character profiles from the raw text.
 * Splits on lines that look like character name headings (e.g. "## Name" or "Name:").
 */
function populateCharacters(text) {
    const placeholder = document.getElementById('characters-placeholder');
    const output = document.getElementById('characters-output');
    if (!output) return;

    output.innerHTML = '';

    // Split on lines that are headings: start with #, or are ALL CAPS short lines, or "Name:" pattern
    const lines = text.split('\n');
    let cards = [];
    let currentName = null;
    let currentBody = [];

    const isHeading = line => {
        const t = line.trim();
        return (
            /^#{1,3}\s+.+/.test(t) ||                          // Markdown heading
            (/^[A-Z][A-Z\s\-']{2,40}:?$/.test(t) && t.length < 50) || // ALL CAPS
            /^\*\*[^*]+\*\*$/.test(t)                          // **Bold**
        );
    };

    const cleanHeading = line => line.replace(/^#+\s*/, '').replace(/\*\*/g, '').replace(/:$/, '').trim();

    for (const line of lines) {
        if (isHeading(line) && line.trim()) {
            if (currentName) cards.push({ name: currentName, body: currentBody.join('\n').trim() });
            currentName = cleanHeading(line);
            currentBody = [];
        } else {
            currentBody.push(line);
        }
    }
    if (currentName) cards.push({ name: currentName, body: currentBody.join('\n').trim() });

    // Fallback: no headings detected — show as single card
    if (cards.length === 0 || (cards.length === 1 && !cards[0].name)) {
        cards = [{ name: 'Character Profiles', body: text.trim() }];
    }

    cards.forEach(({ name, body }) => {
        if (!body && !name) return;
        const card = document.createElement('div');
        card.className = 'character-card';
        card.innerHTML = `<h3>${escHtml(name)}</h3><p>${escHtml(body).replace(/\n/g, '<br>')}</p>`;
        output.appendChild(card);
    });

    if (placeholder) placeholder.style.display = 'none';
    output.style.display = 'flex';
}

/**
 * Parse sound design notes from the raw text.
 * Splits on scene headings.
 */
function populateSound(text) {
    const placeholder = document.getElementById('sound-placeholder');
    const output = document.getElementById('sound-output');
    if (!output) return;

    output.innerHTML = '';

    const lines = text.split('\n');
    let scenes = [];
    let currentScene = null;
    let currentBody = [];

    const isSceneHeading = line => {
        const t = line.trim();
        return (
            /^(Scene\s+\d+|INT\.|EXT\.)/i.test(t) ||
            /^#{1,3}\s+Scene/i.test(t) ||
            /^\*\*Scene/i.test(t)
        );
    };

    const cleanScene = line => line.replace(/^#+\s*/, '').replace(/\*\*/g, '').trim();

    for (const line of lines) {
        if (isSceneHeading(line)) {
            if (currentScene) scenes.push({ heading: currentScene, body: currentBody.join('\n').trim() });
            currentScene = cleanScene(line);
            currentBody = [];
        } else {
            currentBody.push(line);
        }
    }
    if (currentScene) scenes.push({ heading: currentScene, body: currentBody.join('\n').trim() });

    if (scenes.length === 0) {
        scenes = [{ heading: 'Sound Design Notes', body: text.trim() }];
    }

    scenes.forEach(({ heading, body }) => {
        if (!body && !heading) return;
        const scene = document.createElement('div');
        scene.className = 'sound-scene';
        scene.innerHTML = `<h3>${escHtml(heading)}</h3><p>${escHtml(body).replace(/\n/g, '<br>')}</p>`;
        output.appendChild(scene);
    });

    if (placeholder) placeholder.style.display = 'none';
    output.style.display = 'flex';
}

// ── Export ───────────────────────────────────────────────────────────────────
function exportSection(section, fmt) {
    window.location.href = `/download/${section}/${fmt}`;
}

// ── Utility ──────────────────────────────────────────────────────────────────
function escHtml(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
