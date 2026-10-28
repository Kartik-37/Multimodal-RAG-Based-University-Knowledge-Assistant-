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

from nicegui import app, ui

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

/* Semantic Utility Classes (Avoid Inline Hex) */
.bg-canvas { background-color: var(--color-ivory) !important; }
.bg-surface { background-color: var(--color-surface-parchment) !important; }
.bg-surface-elevated { background-color: #FAF6F0 !important; }
.bg-surface-pure { background-color: #FFFFFF !important; }
.bg-surface-navy { background-color: var(--color-atlas-navy) !important; }
.bg-primary-navy { background-color: var(--color-atlas-navy) !important; }
.bg-gold-light { background-color: var(--color-gold-light) !important; }

/* Quasar Focus-Helper Suppression - Eliminate murky, muddy hover overlays */
.q-btn .q-focus-helper,
.q-btn:hover .q-focus-helper,
.q-btn:focus .q-focus-helper,
.q-btn--actionable:hover .q-focus-helper {
    display: none !important;
    opacity: 0 !important;
}

/* Primary Button Styling & Intentional Hover */
.bg-primary, .q-btn.bg-primary, .q-btn--standard.bg-primary, .q-btn.text-white {
    background-color: #0E1D61 !important;
    background: #0E1D61 !important;
    color: #FAF6F0 !important;
    box-shadow: none !important;
    transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease !important;
}

.bg-primary:hover, .q-btn.bg-primary:hover, .q-btn--standard.bg-primary:hover, .q-btn.text-white:hover {
    background-color: #1B2D7C !important;
    background: #1B2D7C !important;
    color: #FFFFFF !important;
    box-shadow: none !important;
}

.text-primary, .q-btn.text-primary {
    color: #0E1D61 !important;
}

/* Outline Buttons */
.q-btn--outline.text-primary, .q-btn--outline {
    border-color: #D8CFBF !important;
    color: #0E1D61 !important;
    background-color: transparent !important;
    box-shadow: none !important;
    transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease !important;
}

.q-btn--outline:hover {
    background-color: #F5F0E8 !important;
    border-color: #B89A5A !important;
    color: #0E1D61 !important;
    box-shadow: none !important;
}

/* Flat Buttons (including view switchers and icon buttons) */
.q-btn--flat.text-primary:not(.filter-pill-selected):not(.bg-primary-navy):not(.view-switcher-pill-active) {
    color: #0E1D61 !important;
}

.q-btn--flat:not(.filter-pill-selected):not(.bg-primary-navy):not(.view-switcher-pill):not(.view-switcher-pill-active):hover {
    background-color: rgba(14, 29, 97, 0.06) !important;
    color: #0E1D61 !important;
    box-shadow: none !important;
}

.text-primary-navy { color: var(--color-atlas-navy) !important; }
.text-secondary-navy { color: var(--color-atlas-navy-muted) !important; }
.text-gold { color: var(--color-gold) !important; }
.text-gold-hover { color: var(--color-gold-hover) !important; }
.text-inverted { color: #FAF6F0 !important; }

/* Authoritative Selected Filter Pill & Navy Button Contrast */
.q-btn.text-inverted, .q-btn.text-inverted .q-btn__content, .q-btn.text-inverted .q-btn__content *,
.q-btn.bg-primary-navy, .q-btn.bg-primary-navy .q-btn__content, .q-btn.bg-primary-navy .q-btn__content *,
.q-btn.bg-surface-navy, .q-btn.bg-surface-navy .q-btn__content, .q-btn.bg-surface-navy .q-btn__content *,
.filter-pill-selected, .filter-pill-selected .q-btn__content, .filter-pill-selected .q-btn__content *,
.q-btn--flat.filter-pill-selected, .q-btn--flat.filter-pill-selected .q-btn__content, .q-btn--flat.filter-pill-selected .q-btn__content *,
.q-btn--flat.bg-primary-navy, .q-btn--flat.bg-primary-navy .q-btn__content, .q-btn--flat.bg-primary-navy .q-btn__content * {
    color: #FFFFFF !important;
    background-color: #0E1D61 !important;
    box-shadow: none !important;
    transition: background-color 0.15s ease, color 0.15s ease !important;
}

.filter-pill-selected:hover,
.filter-pill-selected:hover .q-btn__content,
.filter-pill-selected:hover .q-btn__content *,
.q-btn--flat.filter-pill-selected:hover,
.q-btn.bg-primary-navy:hover {
    background-color: #1B2D7C !important;
    color: #FFFFFF !important;
}

.q-btn:active {
    transform: none !important;
}

.q-btn:focus-visible {
    outline: 2px solid #0E1D61 !important;
    outline-offset: 2px !important;
}

.border-subtle { border-color: var(--color-border-warm) !important; }
.border-gold { border-color: var(--color-gold) !important; }
.border-navy { border-color: var(--color-atlas-navy) !important; }

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

/* Service Health Board Responsive Utilities */
@media (max-width: 767px) {
    .diagnostics-desktop-header {
        display: none !important;
    }
    .diagnostics-desktop-badge {
        display: none !important;
    }
}
@media (min-width: 768px) {
    .diagnostics-desktop-header {
        display: flex !important;
    }
    .diagnostics-desktop-badge {
        display: flex !important;
    }
    .diagnostics-mobile-badge {
        display: none !important;
    }
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

/* Phase 8: Suppress unwanted white number inside progress bars */
.q-linear-progress .absolute-center,
.q-linear-progress .q-linear-progress__model + div,
.q-linear-progress > .text-white {
    display: none !important;
    opacity: 0 !important;
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
/* Responsive Primary Navigation Visibility */
@media (min-width: 768px) {
    .nav-desktop-links {
        display: flex !important;
    }
    .nav-mobile-toggle {
        display: none !important;
    }
}
@media (max-width: 767px) {
    .nav-desktop-links {
        display: none !important;
    }
    .nav-mobile-toggle {
        display: inline-flex !important;
    }
}

/* Responsive Two-Column Grid for Authentication & Onboarding */
.auth-split-grid {
    display: grid !important;
    grid-template-columns: 1fr !important;
    gap: 2rem !important;
    width: 100% !important;
    align-items: start !important;
    box-sizing: border-box !important;
}

@media (min-width: 1024px) {
    .auth-split-grid {
        grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.95fr) !important;
        gap: 3rem !important;
    }
}

/* Quasar layout header integrity */
.q-header.fixed-top {
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    position: fixed !important;
    z-index: 2000 !important;
}

/* =========================================================================
   Admin Part 9F: Sequential Document Intake Workspace (Two-Step Workflow)
   ========================================================================= */

/* Dedicated sequential intake workspace container */
.upload-intake-workspace {
    width: 100% !important;
}

/* Step 1: Destination field group */
.intake-step-destination {
    display: flex !important;
    flex-direction: column !important;
    gap: 0.375rem !important;
    width: 100% !important;
}

/* Step 2: Document intake field group */
.intake-step-document {
    display: flex !important;
    flex-direction: column !important;
    gap: 0.375rem !important;
    width: 100% !important;
}

/* Clear, semantic intake field label */
.intake-field-label,
.upload-field-label {
    display: inline-block !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.8125rem !important; /* 13px */
    font-weight: 600 !important;
    letter-spacing: 0.015em !important;
    line-height: 1.25rem !important;
    color: #2D3748 !important;
    margin: 0 !important;
}

/* Step number pill badge */
.intake-step-number {
    font-family: 'JetBrains Mono', monospace, sans-serif !important;
    font-size: 0.6875rem !important; /* 11px */
    font-weight: 700 !important;
    color: #B89A5A !important;
    background-color: rgba(184, 154, 90, 0.12) !important;
    padding: 0.1rem 0.35rem !important;
    border-radius: 4px !important;
    line-height: 1 !important;
}

/* Target Course Selector: Proportional, predictable width (max-w-md), warm parchment surface */
.upload-course-select.q-field,
.intake-course-select.q-field {
    width: 100% !important;
    min-height: 46px !important;
    height: 46px !important;
    padding-bottom: 0 !important;
}

.upload-course-select .q-field__inner,
.intake-course-select .q-field__inner {
    min-height: 46px !important;
    height: 46px !important;
    display: flex !important;
    align-items: center !important;
}

.upload-course-select .q-field__control,
.intake-course-select .q-field__control {
    min-height: 46px !important;
    height: 46px !important;
    background-color: #FAF6F0 !important;
    border: 1px solid #D8CFBF !important;
    border-radius: 6px !important;
    padding: 0 0.875rem !important;
    box-shadow: none !important;
    box-sizing: border-box !important;
    transition: border-color 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease !important;
}

.upload-course-select .q-field__control:hover,
.intake-course-select .q-field__control:hover {
    border-color: #B89A5A !important;
    background-color: #F5F0E8 !important;
}

.upload-course-select.q-field--focused .q-field__control,
.intake-course-select.q-field--focused .q-field__control {
    border-color: #0E1D61 !important;
    box-shadow: 0 0 0 2px rgba(14, 29, 97, 0.15) !important;
}

.upload-course-select .q-field__control::before,
.upload-course-select .q-field__control::after,
.intake-course-select .q-field__control::before,
.intake-course-select .q-field__control::after {
    display: none !important;
}

.upload-course-select .q-field__control-container,
.intake-course-select .q-field__control-container {
    height: 44px !important;
    min-height: 44px !important;
    display: flex !important;
    align-items: center !important;
}

.upload-course-select .q-field__native,
.intake-course-select .q-field__native {
    min-height: 44px !important;
    height: 44px !important;
    line-height: 44px !important;
    padding: 0 !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: #0E1D61 !important;
    display: flex !important;
    align-items: center !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

.upload-course-select .q-field__append,
.intake-course-select .q-field__append {
    height: 44px !important;
    min-height: 44px !important;
    padding: 0 !important;
    color: #3A4B7C !important;
    display: flex !important;
    align-items: center !important;
}

.upload-course-select.is-unselected .q-field__native,
.intake-course-select.is-unselected .q-field__native {
    color: #5A6594 !important;
    font-weight: 400 !important;
}

/* Document Intake Surface: Purposeful, distinct interaction area (replaces generic dropzone) */
.document-intake-surface.q-uploader,
.academic-uploader.q-uploader {
    position: relative !important;
    width: 100% !important;
    min-height: 74px !important;
    height: auto !important;
    background-color: #FAF6F0 !important;
    border: 1px solid #D8CFBF !important;
    border-left: 3px solid #B89A5A !important;
    border-radius: 6px !important;
    box-shadow: none !important;
    box-sizing: border-box !important;
    transition: border-color 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease !important;
    overflow: hidden !important;
    cursor: pointer !important;
}

.document-intake-surface.q-uploader:hover,
.academic-uploader.q-uploader:hover {
    border-color: #B89A5A !important;
    border-left-color: #0E1D61 !important;
    background-color: #F5F0E8 !important;
}

.document-intake-surface.q-uploader:focus-within,
.academic-uploader.q-uploader:focus-within {
    border-color: #0E1D61 !important;
    box-shadow: 0 0 0 2px rgba(14, 29, 97, 0.15) !important;
}

.document-intake-surface .q-uploader__header,
.academic-uploader .q-uploader__header {
    background-color: transparent !important;
    background: transparent !important;
    color: #0E1D61 !important;
    border-bottom: none !important;
    padding: 0.875rem 1.25rem !important;
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: flex-start !important;
    text-align: left !important;
    gap: 1rem !important;
    min-height: 72px !important;
    height: auto !important;
    cursor: pointer !important;
    box-sizing: border-box !important;
}

/* Small, tasteful document intake icon */
.document-intake-surface .q-uploader__header::before,
.academic-uploader .q-uploader__header::before {
    content: "post_add";
    font-family: "Material Icons";
    font-size: 1.625rem !important;
    color: #B89A5A;
    line-height: 1;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex-shrink: 0 !important;
    transition: color 0.15s ease !important;
}

.document-intake-surface:hover .q-uploader__header::before,
.academic-uploader:hover .q-uploader__header::before {
    color: #0E1D61 !important;
}

.document-intake-surface .q-uploader__header-content,
.academic-uploader .q-uploader__header-content {
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-start !important;
    justify-content: center !important;
    gap: 0.25rem !important;
    padding: 0 !important;
    min-width: 0 !important;
    flex: 1 1 auto !important;
    cursor: pointer !important;
}

.document-intake-surface .q-uploader__title,
.academic-uploader .q-uploader__title {
    font-size: 0.9375rem !important; /* 15px */
    font-weight: 600 !important;
    color: #0E1D61 !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    line-height: 1.3 !important;
    margin: 0 !important;
    white-space: normal !important;
}

/* Discreet format and size guidance */
.document-intake-surface .q-uploader__header-content::after,
.academic-uploader .q-uploader__header-content::after {
    content: "PDF · DOCX · TXT · Markdown · CSV · Maximum 100 MiB";
    font-size: 0.75rem !important; /* 12px */
    color: #5A6594 !important;
    font-family: 'JetBrains Mono', monospace, sans-serif !important;
    line-height: 1.3 !important;
    margin: 0 !important;
    display: block !important;
}

/* Hide meaningless idle 0.0B / 0.00% counter */
.document-intake-surface .q-uploader__subtitle,
.academic-uploader .q-uploader__subtitle {
    display: none !important;
}

/* Eliminate separate visible Browse File button */
.document-intake-surface .q-uploader__header .q-btn,
.academic-uploader .q-uploader__header .q-btn {
    display: none !important;
}

/* Stretched native file input covering the entire intake surface */
.document-intake-surface .q-uploader__input,
.academic-uploader .q-uploader__input {
    position: absolute !important;
    inset: 0 !important;
    width: 100% !important;
    height: 100% !important;
    opacity: 0 !important;
    cursor: pointer !important;
    z-index: 5 !important;
    display: block !important;
}

.document-intake-surface .q-uploader__list,
.academic-uploader .q-uploader__list {
    display: none !important;
}

.document-intake-surface .q-uploader__file,
.academic-uploader .q-uploader__file {
    background-color: #EDE6DA !important;
    border: 1px solid #D8CFBF !important;
    border-radius: 6px !important;
    margin-top: 0.5rem !important;
}

.document-intake-surface .q-uploader__file-header,
.academic-uploader .q-uploader__file-header {
    color: #0E1D61 !important;
}

/* Mobile responsive adjustments */
@media (max-width: 639px) {
    .document-intake-surface.q-uploader,
    .academic-uploader.q-uploader {
        min-height: 64px !important;
    }

    .document-intake-surface .q-uploader__header,
    .academic-uploader .q-uploader__header {
        padding: 0.75rem 1rem !important;
        gap: 0.75rem !important;
        min-height: 62px !important;
    }

    .document-intake-surface .q-uploader__header::before,
    .academic-uploader .q-uploader__header::before {
        font-size: 1.375rem !important;
    }

    .document-intake-surface .q-uploader__title,
    .academic-uploader .q-uploader__title {
        font-size: 0.875rem !important;
    }

    .document-intake-surface .q-uploader__header-content::after,
    .academic-uploader .q-uploader__header-content::after {
        font-size: 0.6875rem !important;
    }
}


/* Responsive Table Column Utilities */
@media (max-width: 639px) {
    .table-header-row {
        display: none !important;
    }
}

@media (min-width: 768px) {
    .col-course-desktop {
        display: flex !important;
    }
}
@media (max-width: 767px) {
    .col-course-desktop {
        display: none !important;
    }
}

@media (min-width: 640px) {
    .col-meta-desktop {
        display: flex !important;
    }
}
@media (max-width: 639px) {
    .col-meta-desktop {
        display: none !important;
    }
}

/* In-Page View Switcher */
.view-switcher-container {
    display: inline-flex;
    align-items: center;
    background-color: #FAF6F0;
    border: 1px solid var(--color-border-warm);
    border-radius: 8px;
    padding: 3px;
    gap: 4px;
}

/* Suppress all focus-helper, pseudo-elements, and Quasar hover overlays in view switcher */
.view-switcher-container .q-focus-helper,
.view-switcher-container .q-focus-helper::before,
.view-switcher-container .q-focus-helper::after,
.view-switcher-container .q-btn::before,
.view-switcher-container .q-btn::after,
.view-switcher-pill .q-focus-helper,
.view-switcher-pill .q-focus-helper::before,
.view-switcher-pill .q-focus-helper::after,
.view-switcher-pill::before,
.view-switcher-pill::after,
.view-switcher-pill:hover::before,
.view-switcher-pill:hover::after,
.view-switcher-pill:hover .q-focus-helper,
.view-switcher-pill:hover .q-focus-helper::before,
.view-switcher-pill:hover .q-focus-helper::after,
.view-switcher-pill-active .q-focus-helper,
.view-switcher-pill-active .q-focus-helper::before,
.view-switcher-pill-active .q-focus-helper::after,
.view-switcher-pill-active::before,
.view-switcher-pill-active::after,
.view-switcher-pill-active:hover::before,
.view-switcher-pill-active:hover::after,
.view-switcher-pill-active:hover .q-focus-helper,
.view-switcher-pill-active:hover .q-focus-helper::before,
.view-switcher-pill-active:hover .q-focus-helper::after {
    display: none !important;
    content: none !important;
    opacity: 0 !important;
    background: transparent !important;
    background-color: transparent !important;
    box-shadow: none !important;
    outline: none !important;
    border: none !important;
}

.view-switcher-pill {
    padding: 6px 14px;
    font-size: 0.8125rem;
    font-weight: 600;
    border-radius: 6px !important;
    color: var(--color-atlas-navy-muted) !important;
    transition: background-color 0.15s ease, color 0.15s ease !important;
    cursor: pointer;
    text-decoration: none;
    border: none !important;
    background: transparent !important;
    background-color: transparent !important;
    box-shadow: none !important;
    outline: none !important;
}

.view-switcher-pill:hover:not(.view-switcher-pill-active) {
    background: rgba(14, 29, 97, 0.06) !important;
    background-color: rgba(14, 29, 97, 0.06) !important;
    color: var(--color-atlas-navy) !important;
}

/* Active solid pill */
.view-switcher-pill-active,
.view-switcher-pill.view-switcher-pill-active,
.q-btn.view-switcher-pill-active {
    background: #0E1D61 !important;
    background-color: #0E1D61 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    border-radius: 6px !important;
    box-shadow: none !important;
}

.view-switcher-pill-active *,
.view-switcher-pill-active .q-btn__wrapper,
.view-switcher-pill-active .q-btn__content,
.view-switcher-pill-active .q-icon,
.view-switcher-pill-active span {
    color: #FFFFFF !important;
    background: transparent !important;
    background-color: transparent !important;
}

/* Active solid pill on hover: smooth uniform navy #1B2D7C without ANY overlay */
.view-switcher-pill-active:hover,
.view-switcher-pill.view-switcher-pill-active:hover,
.q-btn.view-switcher-pill-active:hover {
    background: #1B2D7C !important;
    background-color: #1B2D7C !important;
    color: #FFFFFF !important;
    box-shadow: none !important;
}

.view-switcher-pill-active:hover *,
.view-switcher-pill-active:hover .q-btn__wrapper,
.view-switcher-pill-active:hover .q-btn__content,
.view-switcher-pill-active:hover .q-icon,
.view-switcher-pill-active:hover span {
    color: #FFFFFF !important;
    background: transparent !important;
    background-color: transparent !important;
}

@media (max-width: 639px) {
    .view-switcher-pill {
        padding: 5px 10px;
        font-size: 0.75rem;
    }
}

/* Linear Progress bar text suppression */
.q-linear-progress div:not(.q-linear-progress__track):not(.q-linear-progress__model) {
    display: none !important;
}
.q-linear-progress__value {
    display: none !important;
}

/* Progressive Disclosure Expandable Document Details */
.doc-expand-btn {
    transition: transform 0.2s ease-in-out;
}
.doc-expand-btn.expanded {
    transform: rotate(180deg);
}

.doc-details-pane {
    background-color: #FAF6F0;
    border-top: 1px dashed var(--color-border-warm);
    animation: fadeIn 0.15s ease-in;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
}

/* =========================================================================
   Admin Part 10B.2: Service Health Board Diagnostics Layout
   ========================================================================= */

@media (min-width: 768px) {
    .diagnostics-desktop-header {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        flex-wrap: nowrap !important;
    }
    .diagnostics-service-row {
        display: flex !important;
        flex-direction: row !important;
        align-items: flex-start !important;
        justify-content: space-between !important;
        flex-wrap: nowrap !important;
    }
    .diagnostics-col-service {
        width: 40% !important;
        max-width: 40% !important;
        flex: 0 0 40% !important;
        box-sizing: border-box !important;
    }
    .diagnostics-col-status {
        width: 18% !important;
        max-width: 18% !important;
        flex: 0 0 18% !important;
        display: flex !important;
        box-sizing: border-box !important;
    }
    .diagnostics-col-diagnostic {
        width: 42% !important;
        max-width: 42% !important;
        flex: 0 0 42% !important;
        box-sizing: border-box !important;
    }
    .diagnostics-mobile-badge {
        display: none !important;
    }
    .diagnostics-desktop-badge {
        display: inline-flex !important;
    }
}

@media (max-width: 767px) {
    .diagnostics-desktop-header {
        display: none !important;
    }
    .diagnostics-service-row {
        display: flex !important;
        flex-direction: column !important;
        gap: 0.625rem !important;
    }
    .diagnostics-col-service,
    .diagnostics-col-status,
    .diagnostics-col-diagnostic {
        width: 100% !important;
        max-width: 100% !important;
        flex: 1 1 100% !important;
    }
    .diagnostics-mobile-badge {
        display: inline-flex !important;
    }
    .diagnostics-desktop-badge {
        display: none !important;
    }
}
</style>
"""


def init_theme() -> None:
    """Inject global design system styling and editorial palette into NiceGUI."""
    app.colors(
        primary=COLOR_DEEP_NAVY,
        secondary=COLOR_GOLD,
        accent=COLOR_GOLD,
        dark=COLOR_DEEP_NAVY,
        positive="#2B580C",
        negative="#9B2226",
        info=COLOR_DEEP_NAVY,
        warning="#805B00",
    )
    ui.add_head_html(GLOBAL_THEME_CSS, shared=True)
    ui.add_head_html(
        """<script>
        if ('scrollRestoration' in history) {
            history.scrollRestoration = 'manual';
        }
        window.addEventListener('pageshow', function() {
            window.scrollTo(0, 0);
        });
        </script>""",
        shared=True,
    )
