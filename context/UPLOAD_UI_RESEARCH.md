# Document Intake UI Research & Design System Analysis

## Overview

This document synthesizes established design-system guidance for document-upload workflows and records how these principles are applied to the redesign of the course document intake interface at `/documents`.

---

## 1. Sources Consulted

1. **GOV.UK Design System — File upload**
   - URL: `https://design-system.service.gov.uk/components/file-upload/`
   - Key Guidance:
     * Keep upload interactions critical, simple, and transparent.
     * Support both primary interaction modes: native file chooser click and drag-and-drop into the intake area.
     * Place clear, explicit labels and concise hint text (accepted formats and maximum file size) directly adjacent to the input.
     * Provide specific, actionable error messages for distinct failure states (e.g. missing file, unsupported format, file exceeds size limit).
     * Provide immediate confirmation of selected files before form submission.

2. **Carbon Design System (IBM) — File Uploader Guidelines & Accessibility**
   - URLs:
     * `https://www.carbondesignsystem.com/building-blocks/core/components/file-uploader/guidelines`
     * `https://www.carbondesignsystem.com/building-blocks/core/components/file-uploader/accessibility`
   - Key Guidance:
     * **Sequential Context / Destination First**: Users must understand *where* a file is being uploaded before initiating the file selection. Forcing unrelated destination selectors and file dropzones onto an arbitrary horizontal baseline creates cognitive confusion and unbalanced geometry.
     * **Single Coherent Drop Surface**: Eliminate secondary "Browse File" buttons when the dropzone itself can be activated. The entire dropzone must serve as a reliable click and drag-and-drop target.
     * **Predictable Control Sizing**: Interactive controls should have predictable, semantic widths proportional to their expected content (e.g. course names), rather than shrinking to content size or stretching uncomfortably across wide viewports.
     * **Stateful Feedback**: Maintain distinct, honest visual states:
       - *Idle*: Clean call-to-action with formats and constraints; suppress idle zero-counters (`0.0B / 0.00%`).
       - *Selected / Transferring*: Display filename, size, and honest progress (indeterminate if server extraction is pending, determinate only when chunk counts are verified).
       - *Completed*: Verified success indicator with a clear action to upload another document without a full page refresh.
       - *Failed*: Safe, normalized error message with a retry mechanism.
     * **Accessibility**: Native `<input type="file">` must remain operable via keyboard (`Space` / `Enter`), focus indicators must meet WCAG 2.1 AA contrast requirements, and status updates must be announced to screen readers.

---

## 2. Practical Application to the Multimodal RAG Knowledge Assistant

| Principle | Previous Failure (Part 9D / 9E) | Applied Solution in Part 9F |
| :--- | :--- | :--- |
| **Workflow Structure** | Side-by-side flexbox/grid forcing Target Course and a long 48px dropzone onto one baseline. Target course shrunk to content (`BCA` ~160px) while dropzone stretched ~900px. | **Sequential Two-Step Intake**: Step 1 (Destination: Target Course in its own dedicated row with responsive width) followed by Step 2 (Document: full-width deliberate intake surface below). |
| **Target Selector Sizing** | Dropdown was constrained by content width, shrinking when short course codes were selected and distorting the page grid. | **Appropriate Width**: Course selector styled at `max-w-md` (~380px–420px), giving ample room for full titles (e.g. "BCA — Bachelor of Computer Applications") without collapsing or over-stretching. |
| **Intake Surface Design** | Relied on Quasar `QUploader` internal headers, pseudo-element text (`::after`), and rigid 48px height limits that expanded to 86px on mobile due to text wrapping. | **Purposeful Surface**: Rebuilt with clean, semantic markup. Modest 72px–80px desktop height, warm parchment surface (`#FAF6F0`), 1px solid border (`#D8CFBF`), 3px gold left accent (`#B89A5A`), clear typography, and integrated format/size guidance. Suppresses Quasar internal clutter. |
| **Mobile Proportions** | Vertical stack forced 86px dropzone, duplicated format chips, and excessive card padding, pushing Search and document table below the fold. | **Compact Vertical Rhythm**: Streamlined sequential flow, compact 64px mobile intake height, single concise guidance line, no duplicate headers or giant cloud icons. |
| **State & Progress Truthfulness** | Indeterminate sweeping bar displayed alongside premature `0/1 chunks (0%)` metric during early extraction. | **Gated Progress**: Indeterminate indicator with stage title only during extraction; quantitative chunk percentages shown strictly when `processed_chunks > 0`. |
| **File Picker Integrity** | Maintained 100% full-surface native input coverage with drag-and-drop and keyboard activation preserved; no fake HTML buttons or synthetic events. | Preserved real `ui.upload` engine, 100 MiB limit (`104,857,600` bytes), and background worker ingestion. |
