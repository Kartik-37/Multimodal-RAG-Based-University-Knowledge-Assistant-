# Frontend Rules — NiceGUI

## Technology

- NiceGUI only.
- Python-first implementation.
- Do not introduce React/Next/Vue/Angular unless the user explicitly changes the decision.
- Keep API/business logic out of page components.

## User experience target

The UI must be:
- simple to understand;
- beautiful without being decorative;
- calm and trustworthy;
- readable for long sessions;
- responsive on desktop/tablet/mobile;
- visually distinct enough to feel designed, not generated from a generic SaaS template.

The user's explicit design preference is stronger than the current screenshot styling.

## Do not do

Do not add visual elements merely because a dashboard template contains them.

Avoid:
- excessive cards;
- gradient backgrounds;
- glassmorphism;
- giant hero copy;
- decorative illustrations that do not aid the task;
- glowing effects;
- repeated badges/pills;
- card lift/scale on hover;
- large motion effects;
- pulsing/spinning decorative icons;
- unnecessary tooltips;
- duplicate navigation;
- fake analytics;
- dense operational data on student pages.

## Motion

Default to no animation.

Use a transition only when it makes an interaction easier to understand. Keep it short and subtle.

Use a progress indicator only when there is a real asynchronous process. A static status label is preferred when it communicates the state clearly.

Honor reduced-motion preferences where the browser/UI framework supports it.

## Visual hierarchy

Every primary page should make these obvious:
1. where the user is;
2. what they can do now;
3. what the primary action is;
4. what happened after the action;
5. how to recover from failure.

Use spacing and typography before adding more containers.

## Student information architecture

Default primary navigation:
- Home
- Ask Assistant
- Courses
- Profile
- History only after persistent history exists.

Keep student pages free of retrieval internals and administrator diagnostics.

## Administrator information architecture

Group administration into a small number of understandable sections:
- Overview
- Knowledge
- Chat/Diagnostics
- Administration
- System
- Profile

Do not expose every technical operation as a top-level navigation item.

## Chat UX

The chat page is the main product experience.

Preferred structure:
- concise page header;
- course/scope selector;
- conversation area;
- readable assistant answer;
- visible citation references;
- source/evidence access near the citation;
- composer fixed or naturally positioned at the bottom;
- clear loading/error state.

Do not fill the chat screen with implementation details such as RRF scores, vector scores, reranker internals, or debugging data for students.

Admin diagnostics may be reachable through a deliberate secondary control.

## Citation UX

Citations should be legible in the answer.

Clicking a citation should open the specific authorized evidence source, ideally at the cited page.

Do not rely on raw HTML/JavaScript hacks when a normal NiceGUI interaction can perform the same action safely.

Citation data is untrusted input. Escape/validate content and do not inject arbitrary document names/snippets into raw HTML.

## Source viewer UX

Keep it focused:
- document name;
- course/context;
- page number;
- source document view;
- cited evidence excerpt when available;
- close action.

Do not require the user to understand authentication tokens, URL parameters, object/embed fallbacks, or internal retrieval metadata.

The same-origin authenticated session should authorize the document request. No main session token may be placed in the URL or read by browser JavaScript.

Do not render every chunk of a large document at once. Bound, paginate, or show only relevant evidence.

## Error states

Never display raw Python exceptions, SQL errors, traceback fragments, provider error payloads, file paths, tokens, or secret configuration.

User-facing error messages should say:
- what failed in plain language;
- whether the user's data is safe;
- what action can recover the task.

Technical detail belongs in structured server logs/telemetry.

## Loading states

Prefer meaningful progress/status:
- Uploading
- Processing
- Indexing
- Ready
- Failed — Retry

A simple text/icon status is enough unless the user benefits from actual progress.

## Accessibility

Required:
- keyboard navigation;
- visible focus;
- semantic labels;
- readable contrast;
- accessible validation/error messages;
- logical tab order;
- usable controls on touch screens;
- reduced motion support.

## Responsive rules

Desktop is not the only layout.

Mobile must have an intentionally designed navigation pattern and usable chat composer. Do not merely compress a multi-column desktop dashboard.

## Component discipline

Create components for repeated meaningful interaction patterns.

Do not wrap every small element in an abstraction.

Keep state ownership easy to understand.

## Visual QA checklist

Check every major route in:
- empty state;
- normal state;
- long-content state;
- error state;
- narrow/mobile viewport;
- keyboard navigation.

For chat specifically verify:
- long question;
- long answer;
- many citations;
- zero citations;
- citation opens source;
- source viewer loads actual document;
- unauthorized document access is denied;
- generation failure does not expose exception text.
