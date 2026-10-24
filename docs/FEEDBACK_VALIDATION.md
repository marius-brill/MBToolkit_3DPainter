# Feedback implementation verification

## Current Font Tool status — October 24, 2026

**Full implementation working and tested (user-confirmed).** This records the user's confirmation
of the completed Font Tool, not a claim that the coding agent ran Painter interactively. Automated
tests provide separate regression evidence. The host checks below remain a reusable checklist for
other projects, Painter versions and edge cases; earlier investigation notes describe the status
when they were written. Pie menus, macros and blending are not covered by this Font Tool confirmation.

## Automated

Local validation on October 24, 2026 (`py -3`): **225 tests passed** (19.44s), Ruff
passed, runtime `compileall` passed, and the fixed-root installable release ZIP built successfully.
No tests were skipped in that run. Painter was not launched interactively by the coding agent.

Run pytest, Ruff and compile checks from the repository root. `tests/test_feedback.py` includes macro targeting/failure/safety, sizing, settings migration backup, and an extracted release import. With PySide6 installed in the external test interpreter, it also starts a real offscreen Qt editor in an isolated subprocess, edits/reorders labels, creates a macro, saves, and renders the preview. Painter itself remains a mocked dependency in that test.

Windows in this checkout uses `py -3`; `python` may be a Store alias. Do not install `substance_painter` with pip. External PySide6 is for optional UI tests only; Painter uses its bundled Qt.

## Painter regression checklist (not independently executed by the coding agent)

The offscreen editor regression checks equal sidebar/button geometry at two window sizes, two-slice swapping, real Qt model row moves, duplicate macro operations, Save/reload and Cancel isolation. This is not an operating-system mouse-drag or in-Painter integration test. Menu punctuation is checked independently from user-authored labels.

Fit diagnostics now record each requested/read-back offset, exported PNG SHA-256 and measured bounds. Rejected writes are separate from exports with unchanged pixels; unchanged signatures do not by themselves prove stale rendering. Adaptive ±0.04/0.12/0.3 probes have a 32-render cap and retain existing determinant/center acceptance thresholds. Nested UV transforms are explicitly assigned back. No event-loop settling or asynchronous cancellation is implemented: host settling has not been established as the cause. Before claiming Fit fixed, compare the helper against the actual mask in Painter, including clipping/mesh coverage, and inspect response/readback logs. If settling is required, use a cancellable staged operation rather than sleeps.

### Refit / stencil repair regression

- Reload the plugin. On an off-center isolated painted patch, Fit, extend/erase the patch, then Refit. Repeat unchanged fits and compare location; test rotation, flips and size −1/0/+1. A calibration failure must retain the prior source/projection rather than report success.
- Check the verification helper is removed and all root visibility/selection is restored on export failure. Expect multiple synchronous exports; measure responsiveness inside Painter.
- For failed/misplaced fits enable `MBTOOLKIT_FONT_DIAGNOSTICS=1`. Inspect `last-fit-coverage.png`, `last-fit-probe.png` under Qt application-local data `MBToolkit_3DPainter/generated` and the `Font fit verification` log. Mesh clipping can make measured centers unreliable; no visual correctness claim is made without these host checks.
- Generate text again to produce `MB_Text_v2_*`. Assign that new resource rather than a broken legacy `MB_Text_*` resource. Confirm its retained PNG exists after the function returns and after restarting Painter; save/reopen and verify no `ResourceImage`/decode errors. Legacy assets are not deleted automatically.
- Validate stencil polarity and mesh-coverage artifacts. The lifecycle correction does not turn UV export into a mesh-independent font renderer.
- Partial stencil coverage now has a conservative whole-source-square recovery path. Test a large
  off-center island, interior holes and a tiny island; confirm no missing letters, final centered output,
  temporary-layer cleanup and selection restoration. The 128px source minimum is not full 2048px fidelity.
- Fit pixel scans use owned coverage buffers and cache unchanged paint. Compare diagnostics export/time
  fields before judging total speed: native exports remain synchronous and are not covered by buffer
  microbenchmarks. Confirm final overlap and placement remain unchanged with diagnostics enabled/disabled.
- Automated coverage includes independent forward-transform simulations, calibration rejection, source/projection rollback and real Qt PNG decoding after the temporary directory exits.

1. Load/reload/disable repeatedly; verify no orphan timers, callbacks, shortcuts or helper layers.
2. Check the blending footer at 100%, 150%, 200% display scale; compare height and clipping.
3. Prepare above root/middle/nested layers, selected effects, selected folders, no selection, multi-selection.
4. Paint/fit; edit text/font/spacing/alignment live. Change selection/project before debounce fires. No wrong-target writes.
5. Undo/redo text and transforms. Confirm controls follow external updates without reapplying undone values.
6. Size −1/0/+1 repeatedly, rotate/flip, refit, save/reopen. Confirm zero baseline, no cumulative scale drift and preserved mirrors.
7. Edit paint, add and erase coverage, refit repeatedly. Check effect UID stays constant and masks are not duplicated.
8. Cancel area edit; verify original mask state returns and strokes remain. Change projects or disable mid-session.
9. Exercise nested visibility/ancestor masks, folder blending/effects, export failure, empty/full coverage and tile/material restrictions. Confirm temporary state is restored.
10. Create stencil resource twice; confirm deduplication, text/font/spacing/polarity, cleanup and manual stencil assignment. Check mesh coverage/color-management artifacts; generation is UV-export based.
11. Compare preview/runtime slices at 1–12 items; labels, drag reorder, keyboard buttons, search, missing/native actions, separate names, Save/Cancel.
12. Build the example macro: create Fill, black mask, mask Fill. Run via pie, inspect targets and history. Test failure on pre-existing mask and missing project; later steps must stop.
13. Delete/rename a referenced macro; verify warning/missing-action behavior and stable IDs. Import/export settings and reject malformed/unsafe macro steps.
14. Extract installable ZIP into a clean plugin directory. Exact root must be MBToolkit_3DPainter, without version suffix. Do not enable a second checkout copy.

## Deliberate first-pass limits

- Legacy pie `actions`/`action_names` arrays are preserved for compatibility; no slice-record migration yet.
- Macro steps are a six-operation allowlist, not arbitrary Painter commands or parameterized expressions. No nested macros or run/test button in the editor; test explicitly through a saved pie.
- Native discovery only includes unique nonempty QAction object names and is host-dependent, not a stable universal Painter command API.
- Stencil resource creation does not activate a native stencil. UV export is not a mesh-independent font rasterizer.
- Fit/refit starts with the UV bounding box and can recover onto a solid painted rectangle with measured
  scaling and final 98% ink overlap. This is conservative, not a globally optimal arbitrary-shape text packer.
  Only single 0–1 tile without layered materials; native mesh-clipping/export equivalence remains unverified.
- Project metadata is persistent but not a transactional layer-stack rollback. Macro failure may leave earlier steps. Refit/export/helper-layer history requires interactive undo validation. Font updates no longer wrap verification exports/selection changes in ScopedModification; history granularity must be checked in Painter.