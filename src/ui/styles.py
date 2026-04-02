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

        /* ================================================================
           SECTION A — DESKTOP BASELINE
           All rules here are identical to the original app.py CSS.
           Zero visual change on PC browsers.
           ================================================================ */

        /* Root font — prevents iOS Safari from auto-zooming when tapping
           an input. Has no visible effect on desktop (16px is the browser
           default already). */
        html { font-size: 16px; }

        /* Sidebar — desktop */
        [data-testid="stSidebar"] {
            min-width: 450px;
            max-width: 500px;
        }

        /* Main container — desktop */
        .stMainBlockContainer {
            max-width: 900px;
            margin: 0 auto;
            padding-left: 3rem;
            padding-right: 3rem;
        }

        /* Chat input — desktop */
        [data-testid="stChatInput"] {
            max-width: 900px;
            margin: 0 auto;
        }

        /* Chat text — justified on desktop */
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
            text-align: justify;
        }

        /* Calendar columns — desktop */
        [data-testid="stSidebar"] [data-testid="column"] {
            padding: 0 2px !important;
        }

        /* Calendar buttons — desktop */
        [data-testid="stSidebar"] [data-testid="column"] button {
            height: 40px !important;
            padding: 0px !important;
            border-radius: 8px !important;
            background: rgba(255, 255, 255, 0.03) !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
        }

        /* Today button highlight — desktop */
        [data-testid="stSidebar"] [data-testid="column"] button[data-testid="baseButton-primary"] {
            border: 1px solid rgba(74, 222, 128, 0.4) !important;
            color: #4ade80 !important;
            font-weight: 700 !important;
        }

        /* Event day buttons — blue tint, circle stays right of number via nowrap.
           box-shadow used instead of border because Streamlit's tertiary button
           default styles set border:none !important and win the cascade. */
        [data-testid="stSidebar"] [data-testid="column"] button[data-testid="baseButton-tertiary"] {
            color: #60a5fa !important;
            border: none !important;
            box-shadow: inset 0 0 0 1px rgba(96, 165, 250, 0.5) !important;
            background: rgba(96, 165, 250, 0.06) !important;
        }

        /* Prevent day number + circle from wrapping to a second line */
        [data-testid="stSidebar"] [data-testid="column"] button p,
        [data-testid="stSidebar"] [data-testid="column"] button span {
            white-space: nowrap !important;
            overflow: hidden !important;
        }

        /* Day header row — desktop */
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

        /* ================================================================
           SECTION B — ALL-SCREEN ADDITIONS
           Chat bubble overflow protection. No visible effect on desktop
           (content is wide enough). Prevents horizontal page scroll on
           mobile when a reply contains a code block or table.
           ================================================================ */

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

        /* ================================================================
           SECTION C — TABLET BREAKPOINT (≤ 768px)
           Only activates on screens narrower than 769px.
           Desktop is completely unaffected.
           ================================================================ */

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

            /* Chat text: left-aligned on narrow screens
               (justified causes wide word-gaps on short lines) */
            [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
                text-align: left !important;
            }

            /* Calendar columns: tighter gutter */
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

        /* ================================================================
           SECTION D — PHONE BREAKPOINT (≤ 480px)
           ================================================================ */

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

            /* Calendar columns: flex fix prevents overflow on 360px phones */
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

        </style>
        """,
        unsafe_allow_html=True,
    )
