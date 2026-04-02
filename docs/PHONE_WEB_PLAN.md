# Plan: Mobile & Desktop Responsive Layout for MCMP Chatbot

## Context

The chatbot currently uses fixed widths throughout (`sidebar: 450–500px`, `main container: 900px`, `calendar: 7 hardcoded columns`). There are no `@media` queries. On a phone, the sidebar causes horizontal scroll, the calendar columns are unreadably small, the chat input scrolls off-screen, and iOS Safari zooms in on text inputs.

**Goal:** Make the UI render cleanly on both desktop (≥ 900px) and mobile (≥ 360px) **without changing the desktop appearance in any way.**

## Critical Files

- **MODIFY**: `app.py` — remove both inline CSS blocks, add import + function call, update day labels and event dot
- **CREATE**: `src/ui/styles.py` — new module consolidating all CSS with responsive media queries
- **MODIFY**: `src/ui/__init__.py` — add one export line

---

## Rollback Instructions

To fully revert to the current state, restore these two blocks to `app.py` and delete `src/ui/styles.py`.

### Original CSS Block 1 (lines 88–110 in current `app.py`)
Goes immediately after `st.set_page_config(...)`, replacing the `inject_global_mobile_css()` call:

```python
    # Custom CSS to widen sidebar and adjust chat container
    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            min-width: 450px;
            max-width: 500px;
        }
        .stMainBlockContainer {
            max-width: 900px;
            margin: 0 auto;
            padding-left: 3rem;
            padding-right: 3rem;
        }
        [data-testid="stChatInput"] {
            max-width: 900px;
            margin: 0 auto;
        }
        /* Justify chat message text */
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
            text-align: justify;
        }
        </style>
    """, unsafe_allow_html=True)
```

### Original CSS Block 2 (lines 196–234 in current `app.py`)
Goes inside `with st.sidebar:`, after the event-day-loading loop, replacing nothing (restore the deleted block):

```python
        # Scoped, safe CSS to tighten the grid and style the container
        st.markdown("""
        <style>
            /* Tighten column spacing for the calendar grid */
            [data-testid="stSidebar"] [data-testid="column"] {
                padding: 0 2px !important;
            }
            
            /* Make calendar buttons perfectly square and uniform */
            [data-testid="stSidebar"] [data-testid="column"] button {
                height: 40px !important;
                padding: 0px !important;
                border-radius: 8px !important;
                background: rgba(255, 255, 255, 0.03) !important;
                border: 1px solid rgba(255, 255, 255, 0.05) !important;
            }

            /* Style Specific Types (e.g., Primary = Today) */
            [data-testid="stSidebar"] [data-testid="column"] button[data-testid="baseButton-primary"] {
                border: 1px solid rgba(74, 222, 128, 0.4) !important;
                color: #4ade80 !important; 
                font-weight: 700 !important;
            }
            
            /* Subtle text styling for the native headers */
            .day-header-row {
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
                padding: 0 10px;
            }
            .day-header-item {
                color: #94a3b8;
                font-weight: 600;
                font-size: 12px;
                width: 14%;
                text-align: center;
            }
        </style>
        """, unsafe_allow_html=True)
```

### Original day-header labels (lines 237–246 in current `app.py`)
```python
        st.markdown("""
        <div class="day-header-row">
            <span class="day-header-item">Mo</span>
            <span class="day-header-item">Tu</span>
            <span class="day-header-item">We</span>
            <span class="day-header-item">Th</span>
            <span class="day-header-item">Fr</span>
            <span class="day-header-item">Sa</span>
            <span class="day-header-item">Su</span>
        </div>
        """, unsafe_allow_html=True)
```

### Original event dot line (line 262 in current `app.py`)
```python
                        button_label = f"{day} 🔵" if has_event else str(day)
```

---

## Implementation Steps

### Step 1 — Create `src/ui/styles.py`

Create the file with a single public function `inject_global_mobile_css()`. The function makes **one** `st.markdown()` call with a complete `<style>` block.

The CSS is organized in 4 sections:

---

**Section A — Desktop baseline**
All rules here are **identical to the current CSS** — zero visual change on PC. Both existing CSS blocks (block 1 and block 2) are reproduced here verbatim, then extended with media queries below.

```css
/* ── ROOT FONT ─────────────────────────────────────────────────────
   16px prevents iOS Safari from auto-zooming when tapping an input.
   Has no visual effect on desktop (browsers already default to 16px). */
html { font-size: 16px; }

/* ── SIDEBAR — desktop (unchanged from current) ─────────────────── */
[data-testid="stSidebar"] {
    min-width: 450px;
    max-width: 500px;
}

/* ── MAIN CONTAINER — desktop (unchanged from current) ──────────── */
.stMainBlockContainer {
    max-width: 900px;
    margin: 0 auto;
    padding-left: 3rem;
    padding-right: 3rem;
}

/* ── CHAT INPUT — desktop (unchanged from current) ──────────────── */
[data-testid="stChatInput"] {
    max-width: 900px;
    margin: 0 auto;
}

/* ── CHAT TEXT — justified on desktop (unchanged from current) ───── */
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
    text-align: justify;
}

/* ── CALENDAR COLUMNS — desktop (unchanged from current) ────────── */
[data-testid="stSidebar"] [data-testid="column"] {
    padding: 0 2px !important;
}

/* ── CALENDAR BUTTONS — desktop (unchanged from current) ────────── */
[data-testid="stSidebar"] [data-testid="column"] button {
    height: 40px !important;
    padding: 0px !important;
    border-radius: 8px !important;
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
}

/* ── TODAY BUTTON HIGHLIGHT — desktop (unchanged from current) ───── */
[data-testid="stSidebar"] [data-testid="column"] button[data-testid="baseButton-primary"] {
    border: 1px solid rgba(74, 222, 128, 0.4) !important;
    color: #4ade80 !important;
    font-weight: 700 !important;
}

/* ── DAY HEADER ROW — desktop (unchanged from current) ──────────── */
.day-header-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    padding: 0 10px;
}
.day-header-item {
    color: #94a3b8;
    font-weight: 600;
    font-size: 12px;
    width: 14%;
    text-align: center;
}
```

---

**Section B — All-screen additions**
Chat bubble overflow protection. These rules have no visible effect on desktop (content is wide enough). They prevent horizontal page scroll on mobile when a reply contains a code block or table.

```css
/* ── CHAT BUBBLES: overflow protection (all screens) ────────────── */
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
    overflow-x: auto;
    word-break: break-word;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] pre {
    white-space: pre-wrap;
    word-break: break-all;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] table {
    display: block;
    overflow-x: auto;
}
```

---

**Section C — Tablet breakpoint `@media (max-width: 768px)`**
Only activates on screens narrower than 769px. Desktop is completely unaffected.

```css
@media (max-width: 768px) {

    /* Sidebar: overlay at 85% viewport width instead of fixed 450px */
    [data-testid="stSidebar"] {
        min-width: 85vw !important;
        max-width: 85vw !important;
    }

    /* Main container: reduce side padding */
    .stMainBlockContainer {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* Chat input: pin to bottom of viewport like a native messenger */
    [data-testid="stChatInput"] {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        max-width: 100% !important;
        margin: 0 !important;
        padding: 0.5rem 1rem !important;
        background: var(--background-color, #0e1117) !important;
        z-index: 999 !important;
    }

    /* Push messages up so the last one is not hidden behind the pinned input */
    [data-testid="stChatMessageContainer"],
    .stMainBlockContainer {
        padding-bottom: 80px !important;
    }

    /* Chat text: left-aligned on narrow screens (justified causes wide word-gaps) */
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
        text-align: left !important;
    }

    /* Calendar columns: tighter gutter on mobile */
    [data-testid="stSidebar"] [data-testid="column"] {
        padding: 0 1px !important;
    }

    /* Calendar buttons: square via aspect-ratio; 44px minimum touch target */
    [data-testid="stSidebar"] [data-testid="column"] button {
        height: auto !important;
        aspect-ratio: 1 / 1 !important;
        font-size: 0.75rem !important;
        padding: 0 !important;
        min-height: 44px !important;
    }

    /* Day header font: slightly smaller */
    .day-header-item {
        font-size: 10px;
    }
}
```

---

**Section D — Phone breakpoint `@media (max-width: 480px)`**

```css
@media (max-width: 480px) {

    /* Minimal side padding on very small phones */
    .stMainBlockContainer {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }

    /* Month/year heading: slightly smaller */
    [data-testid="stSidebar"] h4 {
        font-size: 0.9rem !important;
    }

    /* Calendar columns: flex fix prevents columns overflowing on 360px phones */
    [data-testid="stSidebar"] [data-testid="column"] {
        flex: 1 1 0 !important;
        min-width: 0 !important;
        padding: 0 1px !important;
    }

    /* Calendar buttons: very compact */
    [data-testid="stSidebar"] [data-testid="column"] button {
        font-size: 0.65rem !important;
        border-radius: 4px !important;
    }
}
```

---

**Full module structure:**

```python
import streamlit as st

def inject_global_mobile_css() -> None:
    """
    Inject all layout and responsive CSS into the Streamlit app.

    Consolidates the two CSS blocks previously inline in app.py and adds
    @media query overrides for tablet (≤ 768px) and phone (≤ 480px).

    Desktop appearance is identical to before — all mobile rules are
    wrapped in @media queries that do not fire on wide viewports.

    Call this once, immediately after st.set_page_config().
    """
    st.markdown(
        """
        <style>
        /* ... Section A + B + C + D ... */
        </style>
        """,
        unsafe_allow_html=True,
    )
```

---

### Step 2 — Modify `app.py`

**2a — Add import** (after existing imports, around line 6):
```python
from src.ui.styles import inject_global_mobile_css
```

**2b — Replace CSS block 1 (lines 88–110)** with a single call:
```python
    inject_global_mobile_css()
```
The comment line above it (`# Custom CSS to widen sidebar...`) can also be removed.

**2c — Remove CSS block 2 (lines 196–234)** entirely. The CSS is now inside `styles.py`.

**2d — Shorten day-header labels (lines 237–245):**
Change the seven `<span>` strings from two-letter to single-letter:

| Before | After |
|--------|-------|
| `Mo` | `M` |
| `Tu` | `T` |
| `We` | `W` |
| `Th` | `T` |
| `Fr` | `F` |
| `Sa` | `S` |
| `Su` | `S` |

The surrounding `<div class="day-header-row">` / `</div>` HTML is unchanged.

**2e — Replace event dot (line 262):**
```python
# Before:
button_label = f"{day} 🔵" if has_event else str(day)
# After:
button_label = f"{day}·" if has_event else str(day)
```
`·` is Unicode U+00B7 (middle dot). The `🔵` emoji is a wide character that forces the button label to a second line inside compact 7-column calendar cells on mobile. The middle dot fits inline at any size.

---

### Step 3 — Update `src/ui/__init__.py`

Add one line (file is currently empty/stub):
```python
from src.ui.styles import inject_global_mobile_css  # noqa: F401
```

---

## Execution Order

| # | Action | File | Notes |
|---|--------|------|-------|
| 1 | Create `styles.py` with full CSS | `src/ui/styles.py` | New file |
| 2 | Add import | `app.py` ~line 6 | |
| 3 | Replace CSS block 1 with function call | `app.py` lines 88–110 | |
| 4 | Remove CSS block 2 | `app.py` lines 196–234 | |
| 5 | Shorten day labels | `app.py` lines 237–245 | |
| 6 | Replace `🔵` with `·` | `app.py` line 262 | |
| 7 | Update `__init__.py` | `src/ui/__init__.py` | |

---

## Verification

**Desktop (PC browser — no change expected):**
- `streamlit run app.py`
- At full width (≥ 900px): sidebar 450–500px, main content max 900px centered — **visually identical to current**
- Shrink browser to ~1024px: still no horizontal scroll, layout holds
- DevTools: no CSS errors in console

**Tablet simulation (Chrome DevTools — 768px):**
- Sidebar overlay: opens to 85vw, closes cleanly
- Main container padding visibly reduced
- Chat input pinned at bottom of viewport
- Calendar buttons remain square and legible
- Messages have enough bottom padding to not be hidden behind the pinned input

**Phone simulation (Chrome DevTools — 390px, "iPhone 14 Pro" preset):**
- 7 calendar columns all visible, single-letter headers (`M T W T F S S`), no horizontal overflow
- Event days show `·` dot inline with day number — no wrapping
- Chat bubbles: text wraps cleanly; code blocks scroll horizontally within the bubble without scrolling the whole page
- Chat input is at the bottom; tapping it does NOT zoom the page (root `font-size: 16px`)
- `◀` / `▶` navigation buttons have comfortable tap areas

**Real device smoke test (recommended):**
```bash
streamlit run app.py --server.address 0.0.0.0
```
Open on iPhone (Safari) and Android (Chrome). Verify: no document-level horizontal scroll, sidebar opens/closes, calendar fits on screen, chat input is reachable.

---

## Known Follow-Up (not in this plan's scope)

**iOS Safari safe-area inset**: The iOS Safari bottom navigation bar can overlap `position: fixed; bottom: 0` on some iPhones. If reported after testing, add one line to the `[data-testid="stChatInput"]` rule in the 768px media block:
```css
padding-bottom: calc(0.5rem + env(safe-area-inset-bottom)) !important;
```
This is a one-line addition to `styles.py`, no structural change required.
