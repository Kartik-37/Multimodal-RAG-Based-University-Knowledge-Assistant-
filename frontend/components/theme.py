"""Design System and Theme Tokens for NiceGUI Presentation Layer.

Establishes an editorial academic, atlas-inspired visual language grounded in:
- Ivory: #E8E0D2 (primary canvas & page background)
- Gold: #B89A5A (refined rules, accents, active indicators, and citation markers)
- Deep Atlas Navy: #0E1D61 (primary typography, major chrome, and prominent actions)

Typography:
- Primary UI & Body: Plus Jakarta Sans
- Editorial Headings & Display: Source Serif 4
- Code & Citations: JetBrains Mono
"""

from nicegui import ui

# ------------------------------------------------------------------------------
# 1. Authoritative Palette Tokens (Ivory / Gold / Deep Atlas Navy)
# ------------------------------------------------------------------------------
COLOR_IVORY = "#E8E0D2"
COLOR_GOLD = "#B89A5A"
COLOR_GOLD_HOVER = "#9E8347"
COLOR_GOLD_LIGHT = "#F3EBDD"
COLOR_DEEP_NAVY = "#0E1D61"
COLOR_DEEP_NAVY_HOVER = "#1B2D7C"
COLOR_DEEP_NAVY_MUTED = "#3A4B7C"

# Semantic Surface & Chrome Tokens
COLOR_CANVAS = "#E8E0D2"  # Primary page/canvas background
COLOR_SURFACE = "#F5F0E8"  # Soft warm parchment surface
COLOR_SURFACE_LIGHT = "#FFFFFF"  # Pure crisp surface
COLOR_SURFACE_ELEVATED = "#EDE6DA"  # Elevated warm surface
COLOR_SURFACE_NAVY = "#0E1D61"  # Dark navy container / header surface

# Borders & Separators
COLOR_BORDER = "#D8CFBF"  # Subtle warm divider
COLOR_BORDER_STRONG = "#B89A5A"  # Gold accent rule
COLOR_BORDER_LIGHT = "#E2DAD0"

# Typography Tokens
COLOR_TEXT_PRIMARY = "#0E1D61"  # Deep Atlas Navy for headings & high readability
COLOR_TEXT_SECONDARY = "#3A4B7C"  # Refined supporting text
COLOR_TEXT_MUTED = "#6B7B9E"  # Subtle captions & timestamps
COLOR_TEXT_INVERTED = "#FAF6F0"  # Text on navy surfaces
COLOR_TEXT_GOLD = "#9E8347"  # Emphasized gold text with adequate contrast

# Status & Feedback Tokens (harmonized with warm palette)
COLOR_SUCCESS_BG = "#E2F0D9"
COLOR_SUCCESS_TEXT = "#2B580C"
COLOR_WARNING_BG = "#FFF2CC"
COLOR_WARNING_TEXT = "#805B00"
COLOR_DANGER_BG = "#FDE8E8"
COLOR_DANGER_TEXT = "#9B2226"
COLOR_INFO_BG = "#EAEFFC"
COLOR_INFO_TEXT = "#0E1D61"

# Backward-Compatible Aliases
COLOR_BRAND_NAVY = COLOR_DEEP_NAVY
COLOR_BRAND_SLATE = COLOR_DEEP_NAVY_MUTED
COLOR_BRAND_BLUE = COLOR_DEEP_NAVY
COLOR_BRAND_LIGHT_BLUE = COLOR_DEEP_NAVY_HOVER
COLOR_OXFORD_BLUE = COLOR_DEEP_NAVY
COLOR_INSTITUTIONAL_NAVY = COLOR_DEEP_NAVY
COLOR_NAVY_PRIMARY = COLOR_DEEP_NAVY
COLOR_NAVY_INTERACTIVE = COLOR_DEEP_NAVY_HOVER
COLOR_NAVY_HOVER = COLOR_DEEP_NAVY_HOVER
COLOR_ACADEMIC_SLATE_900 = COLOR_TEXT_PRIMARY
COLOR_ACADEMIC_SLATE_800 = COLOR_TEXT_PRIMARY
COLOR_ACADEMIC_SLATE_700 = COLOR_TEXT_SECONDARY
COLOR_ACADEMIC_SLATE_600 = COLOR_TEXT_SECONDARY
COLOR_ACADEMIC_SLATE_500 = COLOR_TEXT_MUTED
COLOR_ACADEMIC_SLATE_400 = "#8E9BB5"
COLOR_ACADEMIC_SLATE_300 = COLOR_BORDER
COLOR_ACADEMIC_SLATE_200 = COLOR_BORDER
COLOR_ACADEMIC_SLATE_100 = COLOR_SURFACE
COLOR_ACADEMIC_SLATE_50 = COLOR_CANVAS

# ------------------------------------------------------------------------------
# 2. Global CSS Stylesheet
# ------------------------------------------------------------------------------
GLOBAL_THEME_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
/* Editorial Academic Typography Tokens */
:root {
    --color-ivory: #E8E0D2;
    --color-gold: #B89A5A;
    --color-gold-hover: #9E8347;
    --color-gold-light: #F3EBDD;
    --color-atlas-navy: #0E1D61;
    --color-atlas-navy-muted: #3A4B7C;
    --color-surface-parchment: #F5F0E8;
    --color-border-warm: #D8CFBF;

    /* Quasar Palette Overrides */
    --q-primary: #0E1D61;
    --q-secondary: #B89A5A;
    --q-accent: #B89A5A;
    --q-dark: #0E1D61;
    --q-positive: #2B580C;
    --q-negative: #9B2226;
    --q-info: #0E1D61;
    --q-warning: #805B00;
}

/* Global Font Configuration */
html, body, .q-page-container, .q-layout, .q-page, #app, .nicegui-content {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    background-color: #E8E0D2 !important;
    color: #0E1D61 !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

.font-editorial, .font-serif, h1, .display-heading {
    font-family: 'Source Serif 4', Georgia, Cambria, serif !important;
}

.font-sans {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

.font-mono {
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace !important;
}

/* Page Container Hierarchy */
.main-page-container {
    padding: 2rem !important;
    max-width: 1440px;
    margin: 0 auto;
    box-sizing: border-box !important;
}

/* Editorial Card & Surfaces (Restrained, Flat, Zero Card-Lift Gimmicks) */
.academic-card, .editorial-card {
    background-color: #FAF6F0 !important;
    border: 1px solid #D8CFBF !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 3px 0 rgba(14, 29, 97, 0.04) !important;
    transition: border-color 0.15s ease !important;
}

.academic-card:hover, .editorial-card:hover {
    border-color: #B89A5A !important;
}

.q-card {
    background-color: #FAF6F0 !important;
    border: 1px solid #D8CFBF !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 3px 0 rgba(14, 29, 97, 0.04) !important;
}

/* Atlas Field-Notes Fine Rule Motifs */
.gold-rule {
    border-top: 1px solid #B89A5A !important;
}
.warm-rule {
    border-top: 1px solid #D8CFBF !important;
}

/* Editorial Inputs & Form Controls */
.minimalist-input .q-field__control,
.minimalist-select .q-field__control {
    border-radius: 6px !important;
    background-color: #FAF6F0 !important;
    border: 1px solid #D8CFBF !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
    min-height: 42px !important;
}

.minimalist-input .q-field__control:hover,
.minimalist-select .q-field__control:hover {
    border-color: #B89A5A !important;
}

.minimalist-input .q-field__control:focus-within,
.minimalist-select .q-field__control:focus-within {
    border-color: #0E1D61 !important;
    box-shadow: 0 0 0 2px rgba(14, 29, 97, 0.15) !important;
}

.minimalist-input .q-field__native,
.minimalist-select .q-field__native {
    font-size: 0.9rem !important;
    color: #0E1D61 !important;
    font-weight: 500 !important;
}

/* Citations & Evidence Treatment (Clear, Gold Accent, Academic) */
.citation-pill {
    display: inline-flex !important;
    align-items: center !important;
    gap: 0.25rem !important;
    padding: 0.15rem 0.45rem !important;
    margin: 0 0.15rem !important;
    border-radius: 4px !important;
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    font-family: 'JetBrains Mono', monospace !important;
    color: #0E1D61 !important;
    background-color: #F3EBDD !important;
    border: 1px solid #B89A5A !important;
    cursor: pointer !important;
    text-decoration: none !important;
    transition: background-color 0.15s ease, color 0.15s ease !important;
}

.citation-pill:hover {
    background-color: #B89A5A !important;
    color: #FFFFFF !important;
}

/* Accessible Keyboard Focus (Deep Atlas Navy Ring) */
*:focus-visible {
    outline: 2px solid #0E1D61 !important;
    outline-offset: 2px !important;
    border-radius: 4px;
}

button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {
    outline: 2px solid #0E1D61 !important;
    outline-offset: 2px !important;
}

/* Markdown Rendering with High Readability */
.safe-markdown {
    line-height: 1.7;
    font-size: 0.95rem;
    color: #0E1D61;
    word-break: break-word;
}

.safe-markdown h1, .safe-markdown h2, .safe-markdown h3, .safe-markdown h4 {
    font-family: 'Source Serif 4', Georgia, serif;
    color: #0E1D61;
    margin-top: 1.25rem;
    margin-bottom: 0.5rem;
    font-weight: 600;
}

.safe-markdown p {
    margin-bottom: 0.85rem;
}

.safe-markdown p:last-child {
    margin-bottom: 0;
}

.safe-markdown ul, .safe-markdown ol {
    margin-left: 1.35rem;
    margin-bottom: 0.85rem;
}

.safe-markdown li {
    margin-bottom: 0.35rem;
}

.safe-markdown code {
    background-color: #F3EBDD;
    color: #0E1D61;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 0.825rem;
    font-family: 'JetBrains Mono', monospace;
    border: 1px solid #D8CFBF;
}

.safe-markdown pre {
    background-color: #0E1D61;
    color: #FAF6F0;
    padding: 0.85rem 1.15rem;
    border-radius: 6px;
    overflow-x: auto;
    margin-bottom: 0.85rem;
    border: 1px solid #B89A5A;
}

.safe-markdown pre code {
    background-color: transparent;
    border: none;
    color: inherit;
    padding: 0;
}

/* Clean Restrained Scrollbars */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: #E8E0D2;
}
::-webkit-scrollbar-thumb {
    background: #D8CFBF;
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: #B89A5A;
}

/* Suppress disruptive Quasar/NiceGUI reconnection popup overlay */
.nicegui-reconnect-alert,
.nicegui-reconnect,
#reconnection_modal,
.q-reconnect,
div[class*="reconnect"] {
    display: none !important;
    opacity: 0 !important;
    pointer-events: none !important;
    visibility: hidden !important;
}

/* Source Viewer Side Drawer */
.source-viewer-card {
    height: 100vh !important;
    max-height: 100vh !important;
    display: flex !important;
    flex-direction: column !important;
    background-color: #FAF6F0 !important;
    border-left: 1px solid #D8CFBF !important;
}

.source-viewer-card .q-tab-panels,
.source-viewer-card .q-tab-panels > .q-panel,
.source-viewer-card .q-tab-panel {
    height: 100% !important;
    flex: 1 1 0% !important;
    display: flex !important;
    flex-direction: column !important;
    padding: 0 !important;
    overflow: hidden !important;
}

.source-viewer-card iframe,
.source-viewer-card object,
.source-viewer-card embed {
    width: 100% !important;
    height: calc(100vh - 160px) !important;
    min-height: 520px !important;
    flex: 1 1 auto !important;
    border: none !important;
    display: block !important;
    background: #FFFFFF !important;
}
</style>
"""


def init_theme() -> None:
    """Inject global design system styling and editorial palette into NiceGUI."""
    ui.add_head_html(GLOBAL_THEME_CSS, shared=True)
