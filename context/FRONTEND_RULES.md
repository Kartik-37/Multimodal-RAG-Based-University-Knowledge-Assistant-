# Frontend Rules

## Framework

Use NiceGUI.

Do not introduce React, Next.js, Vue, Angular, or another frontend framework unless the user explicitly changes the technology decision.

The frontend should remain understandable to a Python developer who is still learning frontend development.

## Strategy

The first frontend is deliberately functional and minimal.

After backend quality gates pass, the frontend becomes a full product experience.

## Design direction

The target is:
- elegant
- calm
- modern
- intelligent without looking "AI generated"
- spacious
- deliberate
- trustworthy
- readable
- visually restrained

Do NOT make:
- a generic SaaS dashboard
- excessive cards
- glowing gradients everywhere
- huge "AI" labels
- unnecessary glassmorphism
- random rounded rectangles
- excessive animations
- noisy sidebars
- fake analytics panels
- decorative UI with no purpose

## Design principle

The interface should feel designed by a thoughtful product designer, not assembled from component-library defaults.

Use:
- strong typography hierarchy
- consistent spacing
- restrained color palette
- subtle borders/shadows
- clear content grouping
- meaningful whitespace
- purposeful motion
- excellent empty states
- excellent loading states
- excellent error states

## Information architecture

The primary experience should make the user's core actions obvious:
- upload/manage knowledge
- search
- ask a question
- inspect evidence
- review conversations/results
- manage account/settings

Do not bury the source evidence behind unnecessary interactions.

## RAG result UX

A good answer should clearly show:
- answer
- citations
- source document
- page/section when available
- enough context to verify the claim

Avoid turning citations into tiny unreadable footnotes.

## Accessibility

Must include:
- keyboard navigation
- visible focus
- semantic HTML
- labels for controls
- appropriate contrast
- reduced-motion support
- accessible errors
- screen-reader-friendly loading states

## Responsive behavior

Design deliberately for:
- desktop
- tablet
- mobile

Do not simply shrink the desktop layout.

## Component discipline

Create reusable components for repeated patterns.

Do not create a component abstraction for every `<div>`.

Keep state ownership understandable.

## Error handling

Errors should explain:
- what happened
- what the user can do next

Never show raw backend exceptions.

## Loading

Use skeletons/progress indicators only where useful.

Avoid spinner-only interfaces for long ingestion tasks. Show meaningful progress/status.

## Visual QA

After implementation:
- inspect every major route
- test empty states
- test long document names
- test long answers
- test many citations
- test errors
- test mobile layout
- test keyboard navigation

Only then consider the frontend complete.


## NiceGUI implementation rules

- Keep UI event handlers thin.
- Call backend/application services rather than duplicating business logic in page code.
- Do not put database access directly into visual components.
- Centralize API/client communication.
- Reuse components when the same interaction appears multiple times.
- Keep state ownership obvious.
- Use meaningful Python names rather than framework-specific cleverness.

## Frontend comments

Comments should explain:
- why a UI state exists;
- how a component communicates with the backend;
- why a loading/error state is necessary;
- any accessibility or responsive-design decision that is not obvious.

Do not add comments to every UI element.
