"""
Design System and Theme Tokens for NiceGUI Presentation Layer.

Establishes a restrained, professional visual language tailored for a university
knowledge assistant. Targets WCAG 2.1 AA engineering design criteria for color
contrast, visible focus indicators, and semantic hierarchy (as an engineering
design target, not a claimed certification).
"""

from nicegui import ui

# ------------------------------------------------------------------------------
# Academic Color Palette Tokens: Oxford Blue & Academic Slate Theme
# ------------------------------------------------------------------------------
# Oxford Blue Spectrum
COLOR_OXFORD_BLUE = "#002147"  # Oxford Blue primary brand color
COLOR_INSTITUTIONAL_NAVY_DARK = "#001833"  # Deep institutional navy
COLOR_INSTITUTIONAL_NAVY = "#002147"  # Primary institutional Oxford Blue
COLOR_INSTITUTIONAL_NAVY_SURFACE = "#0b2b54"  # Oxford Blue secondary surface
COLOR_NAVY_PRIMARY = "#002147"  # Oxford Blue for primary actions
COLOR_NAVY_INTERACTIVE = "#003366"  # Interactive accent & focus ring
COLOR_NAVY_HOVER = "#001a38"  # Hover state for interactive Oxford Blue elements

# Academic Slate Spectrum
COLOR_ACADEMIC_SLATE_900 = "#0f172a"  # High-contrast typography & headings
COLOR_ACADEMIC_SLATE_800 = "#1e293b"  # Secondary chrome & prominent subheaders
COLOR_ACADEMIC_SLATE_700 = "#334155"  # Card titles & emphasized text
COLOR_ACADEMIC_SLATE_600 = "#475569"  # Standard body text & secondary labels
COLOR_ACADEMIC_SLATE_500 = "#64748b"  # Muted metadata, timestamps & captions
COLOR_ACADEMIC_SLATE_400 = "#94a3b8"  # Subtle icon accents & disabled state
COLOR_ACADEMIC_SLATE_300 = "#cbd5e1"  # Active borders & prominent dividers
COLOR_ACADEMIC_SLATE_200 = "#e2e8f0"  # Standard subtle card borders
COLOR_ACADEMIC_SLATE_100 = "#f1f5f9"  # Chip/badge background & muted containers
COLOR_ACADEMIC_SLATE_50 = "#F8F9FA"  # Light Off-White page background

# Backward-compatible Token Aliases
COLOR_BRAND_NAVY = COLOR_INSTITUTIONAL_NAVY_DARK
COLOR_BRAND_SLATE = COLOR_ACADEMIC_SLATE_800
COLOR_BRAND_BLUE = COLOR_OXFORD_BLUE
COLOR_BRAND_LIGHT_BLUE = COLOR_NAVY_INTERACTIVE
COLOR_CANVAS = "#F8F9FA"  # Light Off-White background to reduce eye strain
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
COLOR_INFO_TEXT = "#002147"

# ------------------------------------------------------------------------------
# Global CSS Stylesheet
# ------------------------------------------------------------------------------
GLOBAL_THEME_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
/* Modern Academic Tech Typography */
.font-sans, .font-inter, html, body {
    font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}
.font-mono {
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace !important;
}

/* Quasar Theme Variables: Modern Academic Obsidian & Vibrant Sapphire */
:root {
    --q-primary: #0f172a;
    --q-secondary: #2563eb;
    --q-accent: #3b82f6;
    --q-dark: #020617;
    --q-positive: #10b981;
    --q-negative: #ef4444;
    --q-info: #2563eb;
    --q-warning: #f59e0b;
}

/* Base typography and crisp Modern Academic Canvas */
html, body, .q-page-container, .q-layout, .q-page, #app, .nicegui-content {
    font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background-color: #f8fafc !important;
    color: #0f172a;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* Consistent Main Page Container with Generous Padding */
.main-page-container {
    padding: 2rem !important;
    max-width: 1540px;
    margin: 0 auto;
    box-sizing: border-box !important;
}

/* Minimalist Modern Inputs and Selects */
.minimalist-input .q-field__control,
.minimalist-select .q-field__control {
    border-radius: 10px !important;
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 2px 0 rgba(15, 23, 42, 0.03) !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    min-height: 42px !important;
}
.minimalist-input .q-field__control:hover,
.minimalist-select .q-field__control:hover {
    border-color: #94a3b8 !important;
}
.minimalist-input .q-field__control:focus-within,
.minimalist-select .q-field__control:focus-within {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
}
.minimalist-input .q-field__native,
.minimalist-select .q-field__native {
    font-size: 0.875rem !important;
    color: #0f172a !important;
    font-weight: 500 !important;
}

/* Modern Academic Card Primitives */
.academic-card {
    background: #ffffff;
    border: 1px solid rgba(226, 232, 240, 0.95);
    border-radius: 12px;
    box-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.04);
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.academic-card:hover {
    border-color: #cbd5e1;
}

/* Modern High-Contrast Typography Utilities */
.academic-text-heading {
    color: #0f172a !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}
.academic-text-subheading {
    color: #1e293b !important;
    font-weight: 600 !important;
}
.academic-text-body {
    color: #334155 !important;
    line-height: 1.6 !important;
}
.academic-text-muted {
    color: #475569 !important;
    font-weight: 500 !important;
}

/* Modern Course Card */
.modern-course-card {
    background: #ffffff !important;
    border-radius: 12px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.04) !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
.modern-course-card:hover {
    border-color: #94a3b8 !important;
    box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.06) !important;
}

/* Modern Collapsible Slim Sidebar Styling */
.slim-sidebar-rail {
    background: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
    transition: width 0.2s ease !important;
}
.sidebar-link {
    border-radius: 8px !important;
    transition: background-color 0.15s ease, color 0.15s ease !important;
    font-weight: 500 !important;
}
.sidebar-link-active {
    background: #eff6ff !important;
    color: #1d4ed8 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    border-left: 3px solid #2563eb !important;
}
.sidebar-link:hover:not(.sidebar-link-active) {
    background: #f8fafc !important;
    color: #0f172a !important;
}

/* Sleek Citation Pills */
.citation-pill {
    display: inline-flex !important;
    align-items: center !important;
    gap: 0.25rem !important;
    padding: 0.15rem 0.5rem !important;
    margin: 0 0.15rem !important;
    border-radius: 4px !important;
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    font-family: 'JetBrains Mono', monospace !important;
    color: #1d4ed8 !important;
    background-color: #eff6ff !important;
    border: 1px solid #bfdbfe !important;
    cursor: pointer !important;
    text-decoration: none !important;
    transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease !important;
}
.citation-pill:hover {
    background-color: #dbeafe !important;
    color: #1e40af !important;
    border-color: #60a5fa !important;
}

/* Visible Keyboard Focus Rings (WCAG 2.1 AA Target) */
*:focus-visible {
    outline: 2px solid #2563eb;
    outline-offset: 2px !important;
    border-radius: 6px;
}
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {
    outline: 2px solid #2563eb;
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
    color: #2563eb;
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

/* Suppress disruptive Quasar/NiceGUI reconnection popup overlay across entire app */
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

/* Source Viewer Side Drawer Full Height & Zero Empty Space */
.source-viewer-card {
    height: 100vh !important;
    max-height: 100vh !important;
    display: flex !important;
    flex-direction: column !important;
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
.source-viewer-card .nicegui-html {
    width: 100% !important;
    height: calc(100vh - 170px) !important;
    flex: 1 1 auto !important;
    display: flex !important;
}
.source-viewer-card iframe,
.source-viewer-card object,
.source-viewer-card embed {
    width: 100% !important;
    height: calc(100vh - 170px) !important;
    min-height: 520px !important;
    flex: 1 1 auto !important;
    border: none !important;
    display: block !important;
}
</style>
"""


def init_theme() -> None:
    """Inject global design system styling and institutional palette into NiceGUI."""
    ui.add_head_html(GLOBAL_THEME_CSS, shared=True)
