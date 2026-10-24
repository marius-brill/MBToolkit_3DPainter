# Changelog

## Unreleased

- **Font Tool: full implementation working and tested**, user-confirmed October 24, 2026.
  Includes paint-first Fit / Refit, live editable text masks, persistent relative sizing,
  rotation/mirroring, paint-area editing and durable text stencil generation. Automated regressions
  cover calibration, coverage recovery, rollback, resource lifetime and real offscreen Qt behavior.
  Earlier host-unverified notes below document implementation history, not the current user-confirmed
  Font Tool status; other tools and untested Painter/project combinations retain their validation limits.
- Complete the wider toolkit update: visual pie editing and slice swapping, macro authoring/execution,
  native action discovery, schema-2 settings migration backups, compact blending controls, and a
  fixed-root installable release ZIP built and uploaded by CI, with expanded regression coverage.

- Accelerate Fit coverage scans with owned red/alpha buffers, cache the fixed paint coverage, skip
  disabled diagnostic hashing, reuse consistent local calibration and record verification/export timing.
- Recover stencil generation on partial UV coverage by measuring a complete white source square inside
  a solid island before rendering/cropping text. Preserve hole/clipping checks and reject tiny regions.
  Add real Qt buffer equivalence, partial-island, offset-sign and final stencil cleanup regressions.

- Recover failed paint/text overlap by finding a solid painted rectangle and resizing/recentering
  measured ink; retain the 98% final overlap requirement and bound recovery to four calibration attempts.
- Refit a single toolkit-owned text mask without replacing its source or losing rotation/mirrors;
  restore the previous projection on failure and reset its relative-size baseline on success.
- Retain mask export alpha explicitly, expand adaptive offset probes, verify repeated ink extent,
  and cover hollow/disconnected paint, brute-force rectangle optimality, real PNG recovery and refit rollback.

- Restore explicit boolean `dithering: false` in Fit's Python paint-coverage export preset to fix
  unresolved-parameter failures; keep the separate JavaScript mask export's dithering option omitted.

- Omit optional mask-export dithering to avoid Painter builds rejecting the documented `disabled` value.
- Verify initial text Fit using real layer-mask exports and bounded offset-response calibration instead
  of trusting a guessed UV offset. Guard live edits/selection, verify nested offset readback, reject
  unresponsive/clipped/nonconvergent renders and remove incomplete masks on failure.

- Replace stencil TTF/OTF lookup and Qt font rendering with the selected Painter SourceFont resource
  and documented layer-mask UID export. Remove font-file prompts; add full-square coverage verification,
  ink centering, temporary-layer cleanup and selection restoration. Native export remains host-unverified.

- Replace absolute manual font size with a −1..+1 relative UV-size control (0 = auto-size, 25%..400%),
  non-cumulative scale baselines and per-mask project metadata. Preserve projection rotation/offset/mirroring.
- Add an independent Make stencil button using shared text/font/spacing inputs: flat centered 2048px
  white-on-black alpha rendering, durable PNG import and manual native stencil assignment. Locate the
  original TTF/OTF when the selected Painter resource's font file is inaccessible; no font substitution.

- Enable Font Tool live updates with a 250 ms debounce, optional manual mode, selection-safe cancellation,
  silent selection/font-list loading, and non-modal live error reporting. Keep Update text for immediate apply.

- Match pie/macro sidebar geometry and vertically stack management buttons; remove pie rotation arrows. Pie dragging swaps just two command/label pairs. Macro steps support internal drag/drop with stable operation IDs and duplicate preservation.
- Stop appending ellipses to toolkit menu entries, preserving user-authored punctuation.
- Explicitly write back nested UV transforms, verify probe offset readbacks, log per-probe PNG signatures/bounds and use bounded adaptive calibration distances without weakening acceptance thresholds. Painter Fit root cause and actual-mask equivalence remain unverified.

- Repair stencil source lifetime: decode/normalize/validate exports, atomically retain content-addressed PNGs in application-local data, and import from durable paths rather than deleted temporary files. Regeneration avoids broken legacy name-only resource matches.
- Add bounded rendered-center verification on disposable SourceFont layers for fit/refit and relative sizing, normalize hidden source offsets, and restore previous fit/source state on verification failure. Add optional local coverage/probe diagnostics. Host verification remains required.

- Compact Channel Blending footer without shrinking channel rows.
- Add guarded debounced live text edits, repeated area edit/refit, normalized relative sizing with project metadata, and selection-relative layer creation.
- Add text-to-alpha stencil resource generation with explicit manual native stencil assignment (host rendering unverified).
- Add visual radial pie editing, drag reorder, separate slice labels, function search and best-effort uniquely named native QAction discovery.
- Add structured macro editing/execution for layer creation and mask operations, stop-on-failure reporting and grouped history.
- Add schema-2 migration backup and fixed-root installable ZIP builder; extend pure/controller, extracted-release and optional real offscreen Qt tests.
- These workflows still require in-Painter smoke testing; native discovery does not expose every Painter function.

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
