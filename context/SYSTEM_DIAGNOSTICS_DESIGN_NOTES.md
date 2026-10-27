# System Diagnostics Redesign Notes — Service Health Board

## Design System Research & Foundations

### 1. Carbon Design System — Data Table Guidelines & Accessibility
- **Sources Consulted:**
  - *Carbon Design System — Data Table Guidelines* (`https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines`)
  - *Carbon Design System — Data Table Accessibility* (`https://www.carbondesignsystem.com/building-blocks/core/components/data-table/accessibility`)
- **Key Principles Applied:**
  - **Scannability over Dense Grids:** Tabular data in operational dashboards must prioritize scan speed over mechanical columns. Reducing heavy vertical/horizontal gridlines allows the user's eye to immediately spot abnormal states.
  - **Hierarchy of Operational Telemetry:** Subsystem identity and status take precedence over verbose diagnostic telemetry. Detailed diagnostic messages belong in a dedicated supporting position.
  - **Responsive Adaptation vs. Hidden Horizontal Scrolling:** Complex multi-column data must adapt structurally on mobile. Forcing users to scroll horizontally (`min-w-[760px]`) inside a 390px viewport hides critical diagnostic warnings (like degraded service reasons). The layout must collapse into a linear, readable flow.
  - **Cognitive Load:** Eliminate nested card stacks, redundant section headers, and repetitive subtitles.

### 2. GOV.UK Design System — Status Tags & System Status
- **Source Consulted:**
  - *GOV.UK Design System — Tag Component* (`https://design-system.service.gov.uk/components/tag/`)
- **Key Principles Applied:**
  - **Color Never as Sole Indicator:** Every status badge must pair semantic color with a visible icon and an unequivocal textual label (`Healthy`, `Degraded`, `Unavailable`, `Preview`, `Unknown`).
  - **Proportionate Attention:** Normal/healthy states must remain visually quiet (low saturation, soft tones), while degraded or failed states must be immediately noticeable without overwhelming the entire page with gaudy alert blocks.
  - **Truthful Status Wording:** Clear, unambiguous vocabulary describing the genuine operational condition.

---

## Architectural Concept: The Service Health Board

Rather than a generic HTML four-column data table, the new design organizes the diagnostic experience into three unified, complementary sections:

```
+-----------------------------------------------------------------------------------------+
| [System Diagnostics]                                                                     |
| Deep operational telemetry across relational storage, vector search, inference, workers  |
+-----------------------------------------------------------------------------------------+
| A. CONSOLIDATED OVERALL HEALTH BAR                                                      |
| [Status Badge: DEGRADED] Overall System Status: Degraded      Probe Time: 2026-10-23 UTC |
| Subsystem summary explanation...                           [Refresh Telemetry Button]   |
+-----------------------------------------------------------------------------------------+
| B & C. MONITORED SUBSYSTEM BOARD                                                        |
| +-------------------------------------------------------------------------------------+ |
| | [Icon] API Gateway                        [Healthy Badge]                            | |
| | API request handling & endpoint availability                                        | |
| | Diagnostic: FastAPI core gateway responding normally.                               | |
| +-------------------------------------------------------------------------------------+ |
| | [Icon] PostgreSQL Database                [Healthy Badge]                            | |
| | Relational persistence for records, users, courses, and audit data                  | |
| | Diagnostic: Relational persistence connected and operational.                       | |
| +-------------------------------------------------------------------------------------+ |
| | [Icon] Ollama Services                    [Degraded Badge]                          | |
| | Local language-model inference for grounded assistant responses                     | |
| | Diagnostic: Local Ollama service unreachable at configured endpoint.                 | |
| +-------------------------------------------------------------------------------------+ |
| ...                                                                                     |
+-----------------------------------------------------------------------------------------+
```

### Visual Token & Palette Implementation
- **Institutional Palette:**
  - Background Canvas: Ivory `#E8E0D2`
  - Cards & Elevated Panels: Surface Elevated `#FFFFFF` / Soft warm border `#D8CFBF`
  - Primary Typography: Deep Atlas Navy `#0E1D61`
  - Accents & Rules: Antique Gold `#B89A5A`
- **Functional Semantic Statuses:**
  - **Healthy:** Muted forest green text (`#166534`), soft mint background (`#ECFDF5`), border `#A7F3D0`, `check_circle` icon.
  - **Degraded:** Warm amber text (`#92400E`), soft cream background (`#FFFBEB`), border `#FDE68A`, `warning` icon.
  - **Unavailable / Failed:** Crimson text (`#991B1B`), soft rose background (`#FEF2F2`), border `#FECACA`, `error` icon.
  - **Preview / Simulation:** Slate navy text (`#334155`), cool grey background (`#F1F5F9`), border `#CBD5E1`, `science` icon.
  - **Unknown:** Slate grey text (`#475569`), neutral background (`#F8FAFC`), border `#E2E8F0`, `help_outline` icon.

### Desktop vs. Mobile Layout Execution
- **Desktop (>= 1024px):**
  - Grid with 3 clear horizontal zones:
    1. **Service Identity & Purpose (40%):** Recognizable service icon, bold subsystem title, and clear functional scope explanation.
    2. **Reported Status (18%):** Centered, high-contrast semantic status pill.
    3. **Telemetry Diagnostics (42%):** Unclipped, readable telemetry message in clean sans-serif typography with high-contrast indicator.
  - Restrained fine-line dividers between services (`1px solid #EBE4D8`), eliminating heavy table borders.
- **Mobile (< 1024px, 390x844, 375x667):**
  - **Zero Horizontal Scrolling:** Drops tabular constraints completely.
  - Each subsystem displays as a clean vertical card/row:
    - Line 1: Service Icon + Subsystem Title + Status Badge on the right.
    - Line 2: Purpose statement in quiet secondary navy.
    - Line 3: Live diagnostic readout in a subtle inset container, guaranteeing 100% readability without sideways scrolling or text truncation.
