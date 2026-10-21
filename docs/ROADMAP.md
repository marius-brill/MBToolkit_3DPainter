# Implementation status and next steps

Updated: October 21, 2026. Version remains 0.1.0, development/unverified in Painter.

The original project plan is a historical design reference, not a record of
completed acceptance criteria. The current scope is pie menus, channel blending
and font fills. The Performance Inspector has been removed, not merely hidden,
because it did not measure actual milliseconds. It is not in the feature backlog.

## Current hardening

- Preferences teardown retains a local dialog reference across its close callback.
- Pie editor population blocks selection signals and avoids committing an
  incompletely loaded action list when setting a shortcut.
- Empty/whitespace-only font text is rejected before inserting a fill layer.
- Event startup avoids duplicate subscriptions; shutdown attempts every disconnect
  and retains failed subscriptions for a retry.
- Host-independent controller regression tests use minimal Painter/Qt doubles.
  They do not establish Qt or Painter compatibility.

## Next release gates

1. Verify plugin discovery with the distribution root or copied inner package.
   The repository root now forwards to the runtime when installed directly in the
   user plugins directory; external discovery remains an alternative.
2. Execute MANUAL_TESTS.md in Painter and record exact version, OS, GPU and errors.
3. Validate repeated reload, feature toggles, pending timer cleanup, selection
   events, font API calls, shortcuts and undo/redo.
4. Preserve unexposed font source parameters when changing fonts; validate failure
   rollback for project mutations and settings/feature reconciliation.
5. Expand controller and lifecycle coverage, then add real Qt and Painter tests.
6. Build reproducible release packaging and a tested compatibility matrix before
   describing any host/platform combination as supported.

## Feature backlog

- Pie menus: menu reordering, searchable catalog, icons, keyboard navigation,
  configurable styles, nested menus and explicit script context.
- Blending: validate undo grouping and editing-state behavior inside Painter.
  Compact palette-aware rows, numeric opacity entry, selection-safe writes and
  refresh-time editing guards are implemented; visual/host verification is pending.
- Fonts: preserve source parameters across font changes; add resolution,
  background, projection controls and optional approximate preview. Text color
  is already implemented.
- Foundation: unit-testable controllers, richer capability probes, diagnostics,
  more API-backed commands and version-specific integration adapters.

Viewport stamping is not a supported implementation. Do not replace this
limitation with synthetic input.