# Changelog

## Unreleased

- Match the reference blending layout with dark single-line channel rows, an Apply to all row, explicit Normal/100 resets, mixed-value indicators and API-available blend-mode shortcuts.

- Restore normal-launch discovery for a full checkout installed in Painter's user plugins directory using a root forwarding entry point; test both package layouts.

- Redesign channel blending with compact palette-aware rows, readable labels, a selected-layer header and editable opacity percentages. Reuse rows on refresh and guard edits against selection changes.

- Remove the Performance Inspector, its dock/menu/command, settings toggle and analyzer. Older settings and imported pies discard its retired entries.

- Add a session-only Windows development launcher, read-only Painter console diagnostics, and a smoke-test runbook.

- Fix Preferences teardown when the close callback clears the application reference.
- Block pie-editor population signals that could commit partial or duplicate data.
- Reject empty font text before creating a fill layer.
- Make event subscription startup idempotent and allow disconnect failures to be retried.
- Add host-independent controller regressions and an implementation-status roadmap.
- Explicitly select Ruff correctness rules and expose the public package version.

## [0.1.0] - 2026-10-21

- Initial modular Painter plugin foundation, main menu, settings and independently disabled features.
- Qt radial pie menus with shortcut/editor and explicitly trusted script commands.
- All-channel blend/opacity dock with Painter selection event refresh.
- Read-only structure/performance inspector, **no GPU ms measurements**.
- Editable font-fill tool using Painter `SourceFont`.
- Automated unit tests, GitHub CI, first-party installation instructions.
- Status: requires in-Painter compatibility and interaction smoke testing before stable public release.
