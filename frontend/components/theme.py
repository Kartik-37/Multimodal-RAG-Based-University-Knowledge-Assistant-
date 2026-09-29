"""
Design System and Theme Tokens for NiceGUI Presentation Layer.

Establishes a restrained, professional visual language tailored for a university
knowledge assistant. Targets WCAG 2.1 AA engineering design criteria for color
contrast, visible focus indicators, and semantic hierarchy (as an engineering
design target, not a claimed certification).
"""

from nicegui import ui

# ------------------------------------------------------------------------------
# Academic Color Palette Tokens: Institutional Navy & Academic Slate Theme
# ------------------------------------------------------------------------------
# Institutional Navy Spectrum
COLOR_INSTITUTIONAL_NAVY_DARK = "#0b1528"   # Deep institutional midnight navy (headers, chrome)
COLOR_INSTITUTIONAL_NAVY = "#0f1d38"        # Primary institutional navy
COLOR_INSTITUTIONAL_NAVY_SURFACE = "#16284c"# Navy secondary surface
COLOR_NAVY_PRIMARY = "#1e3a8a"              # Institutional Navy (Blue 900) for primary actions
COLOR_NAVY_INTERACTIVE = "#2563eb"          # Interactive accent & focus ring (Blue 600)
COLOR_NAVY_HOVER = "#1d4ed8"                # Hover state for interactive navy elements

# Academic Slate Spectrum
COLOR_ACADEMIC_SLATE_900 = "#0f172a"        # High-contrast typography & headings
COLOR_ACADEMIC_SLATE_800 = "#1e293b"        # Secondary chrome & prominent subheaders
COLOR_ACADEMIC_SLATE_700 = "#334155"        # Card titles & emphasized text
COLOR_ACADEMIC_SLATE_600 = "#475569"        # Standard body text & secondary labels
COLOR_ACADEMIC_SLATE_500 = "#64748b"        # Muted metadata, timestamps & captions
COLOR_ACADEMIC_SLATE_400 = "#94a3b8"        # Subtle icon accents & disabled state
COLOR_ACADEMIC_SLATE_300 = "#cbd5e1"        # Active borders & prominent dividers
COLOR_ACADEMIC_SLATE_200 = "#e2e8f0"        # Standard subtle card borders
COLOR_ACADEMIC_SLATE_100 = "#f1f5f9"        # Chip/badge background & muted containers
COLOR_ACADEMIC_SLATE_50 = "#f8fafc"         # Clean academic canvas page background

# Backward-compatible Token Aliases
COLOR_BRAND_NAVY = COLOR_INSTITUTIONAL_NAVY_DARK
COLOR_BRAND_SLATE = COLOR_ACADEMIC_SLATE_800
COLOR_BRAND_BLUE = COLOR_NAVY_PRIMARY
COLOR_BRAND_LIGHT_BLUE = COLOR_NAVY_INTERACTIVE
COLOR_CANVAS = COLOR_ACADEMIC_SLATE_50
COLOR_SURFACE = "#ffffff"
COLOR_BORDER = COLOR_ACADEMIC_SLATE_200
COLOR_BORDER_STRONG = COLOR_ACADEMIC_SLATE_300
COLOR_TEXT_PRIMARY = COLOR_ACADEMIC_SLATE_900
COLOR_TEXT_SECONDARY = COLOR_ACADEMIC_SLATE_600
COLOR_TEXT_MUTED = COLOR_ACADEMIC_SLATE_500

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
/* Quasar Theme Variables: Institutional Navy & Academic Slate */
:root {
    --q-primary: #1e3a8a;
    --q-secondary: #475569;
    --q-accent: #2563eb;
    --q-dark: #0b1528;
    --q-positive: #166534;
    --q-negative: #991b1b;
    --q-info: #1e40af;
    --q-warning: #92400e;
}

/* Base typography and smooth institutional rendering */
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

/* Standardized Subtle Card Borders and Shadows */
.q-card {
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.04), 0 1px 2px -1px rgba(15, 23, 42, 0.03) !important;
    border-radius: 0.5rem;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

/* Refined Subtle Shadow Utility Overrides */
.shadow-2xs, .shadow-xs {
    box-shadow: 0 1px 2px 0 rgba(15, 23, 42, 0.03) !important;
}
.shadow-sm {
    box-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.04), 0 1px 2px -1px rgba(15, 23, 42, 0.03) !important;
}
.shadow-md {
    box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.05), 0 2px 4px -2px rgba(15, 23, 42, 0.03) !important;
}
.shadow-lg {
    box-shadow: 0 8px 16px -3px rgba(15, 23, 42, 0.06), 0 3px 6px -2px rgba(15, 23, 42, 0.03) !important;
}
.shadow-xl, .shadow-2xl {
    box-shadow: 0 12px 24px -4px rgba(15, 23, 42, 0.08), 0 4px 8px -3px rgba(15, 23, 42, 0.04) !important;
}

/* Subtle Card Interactive Hover Transitions */
.card-hover:hover, .q-card.hover-lift:hover {
    border-color: #cbd5e1 !important;
    box-shadow: 0 4px 8px -2px rgba(15, 23, 42, 0.06), 0 2px 4px -2px rgba(15, 23, 42, 0.04) !important;
}

/* Modal Dialog Cards: Subtle elevation instead of harsh drop-shadows */
.q-dialog .q-card {
    box-shadow: 0 12px 28px -4px rgba(15, 23, 42, 0.12), 0 4px 10px -3px rgba(15, 23, 42, 0.06) !important;
    border: 1px solid #cbd5e1 !important;
}

/* Custom restrained academic scrollbars */
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
    background-color: #0b1528;
    color: #f8fafc;
    padding: 0.75rem 1rem;
    border-radius: 0.375rem;
    overflow-x: auto;
    margin-bottom: 0.75rem;
    border: 1px solid #1e293b;
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

/* Breadcrumb Navigation Trail Component */
.academic-breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.75rem;
    color: #64748b;
}
.academic-breadcrumb a {
    color: #475569;
    text-decoration: none;
    transition: color 0.15s ease;
}
.academic-breadcrumb a:hover {
    color: #1e3a8a;
    text-decoration: underline;
}
.academic-breadcrumb .active-crumb {
    color: #0f172a;
    font-weight: 600;
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

/* Restrained institutional reconnection notification */
.nicegui-reconnect {
    background-color: rgba(11, 21, 40, 0.94) !important;
    backdrop-filter: blur(8px) !important;
    color: #f8fafc !important;
    font-size: 0.8125rem !important;
    font-weight: 500 !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    box-shadow: 0 8px 20px -4px rgba(0, 0, 0, 0.25) !important;
}
</style>
"""


def init_theme() -> None:
    """Inject global design system styling and institutional palette into NiceGUI."""
    ui.add_head_html(GLOBAL_THEME_CSS, shared=True)
