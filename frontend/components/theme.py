"""
Design System and Theme Tokens for NiceGUI Presentation Layer.

Establishes a restrained, professional visual language tailored for a university
knowledge assistant. Targets WCAG 2.1 AA engineering design criteria for color
contrast, visible focus indicators, and semantic hierarchy (as an engineering
design target, not a claimed certification).
"""

from nicegui import ui

# ------------------------------------------------------------------------------
# Academic Color Palette Tokens
# ------------------------------------------------------------------------------
COLOR_BRAND_NAVY = "#0f172a"  # Slate 900: Institutional chrome, deep contrast
COLOR_BRAND_SLATE = "#1e293b"  # Slate 800: Secondary chrome, headers
COLOR_BRAND_BLUE = "#1d4ed8"  # Blue 700: Primary actions, focused interactive
COLOR_BRAND_LIGHT_BLUE = "#2563eb"  # Blue 600: Links, focus ring
COLOR_CANVAS = "#f8fafc"  # Slate 50: Neutral page background
COLOR_SURFACE = "#ffffff"  # White: Cards and content containers
COLOR_BORDER = "#e2e8f0"  # Slate 200: Subtle card borders
COLOR_BORDER_STRONG = "#cbd5e1"  # Slate 300: Active or focused borders
COLOR_TEXT_PRIMARY = "#0f172a"  # Slate 900: High-contrast body & headings
COLOR_TEXT_SECONDARY = "#475569"  # Slate 600: Secondary descriptions
COLOR_TEXT_MUTED = "#64748b"  # Slate 500: Helper text, metadata

# Semantic Status Tokens (Color + Icon + Text pair)
COLOR_SUCCESS_BG = "#dcfce7"
COLOR_SUCCESS_TEXT = "#166534"
COLOR_WARNING_BG = "#fef3c7"
COLOR_WARNING_TEXT = "#92400e"
COLOR_DANGER_BG = "#fee2e2"
COLOR_DANGER_TEXT = "#991b1b"
COLOR_INFO_BG = "#dbeafe"
COLOR_INFO_TEXT = "#1e40af"

# ------------------------------------------------------------------------------
# Global CSS Stylesheet
# ------------------------------------------------------------------------------
GLOBAL_THEME_CSS = """
<style>
/* Base typography and smooth rendering */
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background-color: #f8fafc;
    color: #0f172a;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* WCAG 2.1 AA Engineering Design Target: Visible Keyboard Focus Rings */
*:focus-visible {
    outline: 2px solid #2563eb !important;
    outline-offset: 2px !important;
    border-radius: 4px;
}

/* Buttons and interactive elements focus transition */
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {
    outline: 2px solid #2563eb !important;
    outline-offset: 2px !important;
}

/* Custom restrained scrollbars */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: #f1f5f9;
}
::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
}

/* Markdown rendered text readability */
.safe-markdown {
    line-height: 1.65;
    font-size: 0.9375rem;
    color: #1e293b;
    word-break: break-word;
}
.safe-markdown p {
    margin-bottom: 0.75rem;
}
.safe-markdown p:last-child {
    margin-bottom: 0;
}
.safe-markdown ul, .safe-markdown ol {
    margin-left: 1.25rem;
    margin-bottom: 0.75rem;
}
.safe-markdown li {
    margin-bottom: 0.25rem;
}
.safe-markdown code {
    background-color: #f1f5f9;
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
    font-size: 0.8125rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    border: 1px solid #e2e8f0;
}
.safe-markdown pre {
    background-color: #0f172a;
    color: #f8fafc;
    padding: 0.75rem 1rem;
    border-radius: 0.375rem;
    overflow-x: auto;
    margin-bottom: 0.75rem;
}
.safe-markdown pre code {
    background-color: transparent;
    border: none;
    color: inherit;
    padding: 0;
}

/* Responsive table container */
.responsive-table-wrapper {
    width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}

/* Screen reader only utility class */
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}
</style>
"""


def init_theme() -> None:
    """Inject global design system styling into the NiceGUI application head."""
    ui.add_head_html(GLOBAL_THEME_CSS, shared=True)
