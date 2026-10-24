# Font Fit investigation — October 24, 2026

## Current status

The user now confirms the **Font Tool full implementation works and is tested** (October 24, 2026).
The investigation below preserves the evidence and remaining edge-case checks from development;
its earlier pending-validation statements are historical, not a reversal of that confirmation.
Automated simulations are still distinct from interactive Painter tests and do not certify every mesh.

## Evidence and regression

- The installed Painter log identifies 11.0.3, build 4609.
- Commit `6b1ef49` (October 22) computed a bounding-box transform and did not render-verify placement.
- The working tree added mask-export calibration and the 98% ink-overlap rejection shown in the report.
- Centering a bounding box does not imply paint containment: a hollow or disconnected patch can have
  zero painted pixels at its center. The previous implementation rejected that case without searching.
- No saved failure capture was found. A host export-coordinate mismatch, mesh clipping or stale render
  has not been proven to explain the user's particular project. Do not present these as established causes.

## Implemented repair

Fit retains render calibration, offset readback and final 98% overlap verification. Failed containment
now triggers a linear-time maximal-rectangle search of actual coverage within the original UV bounds.
The rectangle is scored by how much of the measured ink fits, using its current aspect ratio. Recovery
scales the actual projection, centers it on the solid region and exports again. Three retries are allowed;
each calibration has a 32-observation limit. Sub-four-pixel lettering during recovery is refused.

Mask exports explicitly retain alpha; installed JavaScript documentation exposes `keepAlpha` with a
default of false. No undocumented dithering spelling is supplied. Adaptive offset probes use both signs
at three distances; final repeated observations must preserve ink extent as well as center.

Refit accepts only a single named toolkit SourceFont mask Fill effect, from either the parent layer or
the effect selection. It preserves the source, rotation and mirror signs, never duplicates masks, restores
the prior projection on failure, and records a new relative-size baseline on success. Custom masks are
refused. Rotation/flip/reset now explicitly assign nested UV transformations back for copy-on-get APIs.

## Verification and remaining host checks

Automated coverage includes brute-force comparison of rectangle scores on seeded random grids,
hole/disconnected-region placement with real Qt PNG pixels and a simulated Painter exporter, recovery
resizing, export cleanup, offset calibration, copy-on-get transforms, refit source/mirror/rotation retention,
and rollback. The PNG simulation is not an Adobe renderer integration test.

Reload the plugin before checking Fit in Painter. Test an off-center solid patch, hollow patch and two
separated patches, then extend/erase paint and Fit again on the same mask. Check rotation/mirroring,
size zero after refit, repeated unchanged fits, and failure rollback. Enable `MBTOOLKIT_FONT_DIAGNOSTICS=1`
for local coverage/probe/overlap captures. Compare these with the actual 2D mask, especially on UV-island
boundaries. Export equivalence, mesh clipping, undo history and interactive responsiveness still require
in-Painter validation; the synchronous bounded exports can temporarily block the UI.

## Follow-up: performance and stencil coverage

The user confirmed Fit placement works, but reported poor performance and the stencil full-square
coverage rejection. Fit repeatedly called Qt `pixelColor` across 512px exports. Replacing that path with
owned red/alpha buffers measured five bounds scans at 0.064s instead of 0.946s, and one cached overlap at
0.0068s instead of 0.206s in the external interpreter. These are processing microbenchmarks, not native
Painter wall-clock timings. Paint buffers are reused; disabled diagnostics no longer hash exported PNGs.

Stencil now treats the initial white export as a coverage map. Conservative all-pixels-covered pooling
finds a solid region; a whole white source square is fitted there and verified for expected extent,
interior holes, responsive offsets and repeated final observations. Only then is the background made
black and actual text exported/cropped. A 128px source-square minimum limits extreme enlargement;
this does not promise the fidelity of a full-resolution independent font rasterizer. Tests simulate
partial UV islands with both offset-sign conventions and exercise final centered output and cleanup.

Host timings, actual SourceFont background/wrapping behavior and the user's mesh still need Painter
validation. Do not infer missing-letter safety merely from the bounds of visible glyphs.