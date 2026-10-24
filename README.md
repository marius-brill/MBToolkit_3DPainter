# MBToolkit_3DPainter

**Version:** 0.1.0 (development; Font Tool working and tested, user-confirmed)<br>
**Maintainer:** Marius Brill  
**Requires:** Adobe Substance 3D Painter 10.1+ (Python 3.11 / PySide6)  
**License:** MIT

A modular toolkit for Adobe Substance 3D Painter, to improve on tools and add new ones to speed up workflows.

> **Release status:** The **Font Tool full implementation is working and tested**, as confirmed by the user on October 24, 2026. Automated regression checks supplement that confirmation; they do not replace native Painter rendering tests. Pie menus, macros, Channel Blending and broader compatibility still require their own host validation. Painter 10.1+ is the intended baseline, **not** a tested compatibility guarantee for every release or project.

## Installation

### Development / no copying

Windows users can also use the session-only launcher and diagnostic procedure in
[SMOKE_TEST_RUNBOOK](docs/SMOKE_TEST_RUNBOOK.md).

1. Unzip the package anywhere on your computer.
2. Set the environment variable `SUBSTANCE_PAINTER_PLUGINS_PATH` to the absolute path of the **`painter_python`** directory from this repository (not the plugin folder inside it).
3. Start Painter, then load `MBToolkit_3DPainter` using its Python Plugins menu if not automatically loaded.
4. Look for **MBToolkit** on Painter's top menu bar.

Examples of configuring the variable for the current session (replace `$REPO` or path with your checkout location):

- **Windows PowerShell:** `$env:SUBSTANCE_PAINTER_PLUGINS_PATH = 'D:\dev\MBToolkit_3DPainter\painter_python'` and launch Painter *from that environment*.
- **Linux/macOS shell:** `export SUBSTANCE_PAINTER_PLUGINS_PATH="$PWD/painter_python"` and launch Painter from that shell.

The example Windows path is illustrative; the plugin never embeds it. If you already use this variable for other plugins, consult Painter documentation before replacing its value.

### User plugin directory

If this entire checkout is already directly inside Painter's user `plugins/`
directory as `MBToolkit_3DPainter`, its root forwarding entry point loads the
canonical runtime in place. No environment variable is needed for that layout.
Do not also enable a second copy through an external plugin path.

Copy **`painter_python/plugins/MBToolkit_3DPainter/`** (the folder containing `__init__.py`) into Painter's user Python **`plugins/`** directory, as described in Adobe's [Plugin documentation](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/writing-plugins/substance-painter-plugins). No path editing inside the Python files is required.

## Included features

| Tool | Current behavior | Status |
|---|---|---|
| Pie Menu Creator | Multiple radial pies, equal-angle clickable slices, mouse selection, per-menu shortcuts, command catalog, menu editor, opt-in trusted `.py` scripts | Implemented, host testing pending |
| Channel Blending | Dockable per-channel blend mode + opacity controls; follows selected paint/fill layer | Implemented, host testing pending |
| Font Tool | Paint-first Fit / Refit, editable live text masks, relative sizing, rotation/mirroring, and text stencil generation | Full implementation working and tested (user-confirmed); automated regressions included |

### Feature limitations

- **Text masking, not viewport stamping:** Font Tool uses a procedural `SourceFont` Fill effect in a paint layer's mask. Position that effect using Painter's projection tools. Changing lettering reveals existing paint; it does not move strokes or create paint in previously unpainted areas.
- **Native actions in pies:** Search includes API-backed layer/mask commands, toolkit tools, macros, scripts, and best-effort uniquely named native QActions. Native actions are host-dependent: unnamed/ambiguous actions are excluded and availability is checked again before execution. This is not a guarantee of exposing every Painter function.
- **Custom Python:** Scripts run with the current user's permissions, with the same privileges as Painter. Scripts are disabled unless a user explicitly opts in under Preferences.

## Usage

1. Open **MBToolkit → Preferences → Features** to enable or disable tools.
2. Open **MBToolkit → Pie Menus → Manage Pie Menus** to create/reorder wheels, add registered actions, and assign shortcuts. Shortcuts do not have a default value to avoid unknown native conflicts.
3. Open **MBToolkit → Channel Blending** with one paint or fill layer selected.
4. Open **MBToolkit → Font Tool**, choose **Prepare text area**, and paint a broad patch on the layer content. Enter text, choose a font, select the paint layer and click **Fit / Refit**. Existing text masks load automatically and update live after a short pause. If a layer has several font mask effects, select the specific effect. Older Base Color text fill layers remain unchanged.
5. Under **Preferences → Python Actions**, save a local `.py` file and explicitly enable trusted custom actions. Reopen the Pie Menu Editor to assign it.

Settings are stored outside the installation in the OS-specific Painter user configuration directory (via Qt `QStandardPaths`). Use Preferences to export or import portable JSON.

### Paint-first text placement

Choose **Prepare text area**, paint a broad patch on the new layer's content, select that layer,
then choose **Fit text to painted area**. This attaches an editable text mask to the existing paint,
centers a square text source in the patch's UV bounding box with 10% padding, and enables automatic font sizing.
Select the text layer or its mask Fill effect to load settings automatically, then edit live.
Updates are debounced and guarded against project/selection changes. **Apply now** flushes an edit immediately.
**Size adjustment** ranges from −1 to +1: 0 is auto fit, −1 is quarter size, +1 is four times size.
The fit baseline is saved in project metadata. Refit older masks once before adjusting their relative size.
Alignment and spacing are under the collapsed **Advanced** section. Help is available in tooltips.

This is UV-space placement, not a 3D viewport center or a guarantee of fitting inside irregular strokes.
Use one continuous patch away from seams and tile edges. The initial implementation only accepts an
paint layer with Base Color, a single 0–1 UV tile, and no material layering. New layers appear above the selected owning layer, including inside folders; a selected folder creates a sibling above it.
It temporarily isolates the layer and exports Base Color alpha at 512px, restores visibility,
and deletes the temporary export. No persistent image cache is created. Empty/full-tile coverage is rejected.
The user has confirmed the implemented Font Tool works and is tested; unusual meshes, export behavior and other Painter versions still need project-specific validation.
**Edit painted area** temporarily disables the text mask and selects paint content. Paint or erase, then **Fit / Refit** to reuse the same text effect. **Cancel area edit** restores mask visibility but keeps strokes. Refit preserves rotation, mirror signs and relative size; unrelated/ambiguous masks are not replaced. Nested measurement temporarily isolates the ancestor path and restores visibility/masks. Folder effects/blending can still influence coverage and require host validation.

### Visual pies and macros

The Pie Menu Editor has a left menu list and a radial preview on the right. Click a slice to select it; drag it onto another slice to swap only those two positions, including their custom labels. Other slices stay in place; dropping onto the center, outside, or the same slice does nothing. Both tabs use matching sidebars with vertically stacked New / Duplicate / Delete buttons. Search the function catalog and choose a function independently from its **Slice display name**. Clear the display name to restore the default. Preview clicks never execute commands. Toolkit menu entries no longer append ellipses; punctuation in your own names is preserved.

The **Macros** tab creates bounded declarative sequences. For example: **Create Fill Layer → Add Black Mask to Target → Add Fill to Target Mask**. The last created layer is passed to later mask steps; without a creation step the initial selected owning layer is used. Nested macros, arbitrary code, destructive operations and native UI actions are not macro steps. Execution stops on failure; earlier changes may remain. Compatible operations are grouped in Painter history. Save commits both tabs; Cancel discards both. Settings schema 2 preserves legacy pie arrays and backs up schema-1 settings to `settings.pre-v2.json` on first save.

Macro steps support internal drag-and-drop ordering, including duplicate operations. The up/down buttons remain available. Reordering edits the draft only: Save persists both tabs and Cancel discards draft changes.

### Text stencil resource

Click **Make stencil** inside the Font Tool. It uses the current text, selected font, line spacing and
character spacing to make a 2048 × 2048 grayscale alpha: white lettering on opaque black, centered
horizontally and vertically, with centered lines, 10% padding and no rotation or mirroring. Relative
size, alignment and painted-area placement are intentionally ignored. The exact selected Painter font
resource is rendered by SourceFont on a disposable layer's mask, using the same resource IDs as text
creation, including shelf, project and session fonts. No TTF/OTF lookup, file dialog, Qt font renderer
or system-font substitution is used. The individual mask is exported by layer UID through the documented
`alg.mapexport.save` bridge, not through a composited Base Color/mesh texture export. A white coverage
probe must cover the full output square; otherwise generation stops explicitly to avoid UV-clipped
lettering. Empty or edge-clipped text is rejected. Actual ink is centered with 10% padding after export.
The temporary layer and exports are removed on success/failure, and the original selection is restored.
Existing layers, masks and their visibility are not edited. Temporary operations may appear in history.

The result is imported into the open project as an alpha and revealed in Assets;
**drag it to Painter's Stencil slot manually**. The PNG is retained atomically in Qt's application-local
data directory under `MBToolkit_3DPainter/generated`. Do not delete that directory while assets use it.
The complete Font Tool workflow is user-confirmed working and tested. Host-double tests cannot establish
native mask export, coverage or stencil behavior on every project; validate unusual meshes separately.

### Refit placement verification

Fit/refit verifies rendered placement rather than assuming the UV offset's sign and transform order. A bounded numerical calibration corrects placement and rejects empty, clipped, unresponsive or nonconvergent results before committing the projection. Font-source offset is reset to zero and vertical alignment to Middle to avoid a second hidden translation. Existing rotation, mirroring, text and horizontal alignment are retained. Multiple 512px exports can make these actions slower, and UV islands/mesh coverage can prevent calibration: in that case keep the previous placement and use manual projection instead. See the current implementation details below.

**Current checkout correction:** initial **Fit to painted area** now verifies the actual newly added mask
by UID at 512px and calibrates its UV offset against observed render motion (up to 32 observations per attempt).
It blocks live-update feedback during Fit, checks selection and offset readback, requires the final ink
bounds inside the painted bounding box, and removes its incomplete mask if verification fails. No
guessed-position success fallback is used. Fit also requires at least 98% of measured text ink to overlap
painted pixels, using alpha-composited red values rather than transparent RGB. If centered text misses
paint or exceeds its bounds, a linear-time solid-rectangle search finds an alternative painted region,
then scales and recenters the actual measured ink with padding. Recovery is limited to three retries
(128 observations total), and rejects lettering narrower than four pixels at the fitting resolution.
Refitting reuses a single toolkit-owned `MB Text Mask`, preserves its source, rotation and mirrors,
and restores the previous projection on failure. Other masks are refused rather than replaced.
Relative sizing currently preserves the numeric UV offset but does not run this centering calibration.
Fit is user-confirmed working; mesh-clipped masks outside the tested workflow still need project-specific validation.

Fit uses owned red/alpha byte buffers instead of per-pixel Qt calls, caches paint coverage within
the operation, and skips diagnostic PNG hashing when diagnostics are disabled. Calibration reuses its
local motion matrix only while measured motion agrees, and recalibrates on disagreement. Diagnostics
include export counts, export time and total verification time. Exports are still synchronous.

Stencil generation no longer requires UV coverage across the entire tile. When the white coverage probe
is partial, it locates a conservatively covered square, places and calibrates the **whole white source
square** there, verifies its dimensions and checks for interior holes before rendering text. The final
text is cropped from that verified source and centered on a 2048px black canvas. Coverage smaller than
128 source pixels is refused to avoid extreme enlargement. This remains mesh-dependent native rendering,
not a mesh-independent rasterizer; unusual islands can still fail safely. Partial-coverage calibration
has a global 64-observation cap and may take longer than full-tile stencil export.

Mask export deliberately omits optional dithering: some Painter builds reject the documented
`disabled` spelling with a parser expecting `disbaled`. We do not send either spelling.

Fit reports its current stage and keeps its result visible while the same paint layer remains selected.
Busy/loading/disposed guards report why Fit cannot start. Errors still show a warning dialog, and failure
removes only the newly created mask, not the painted content. Stage labels repaint without processing
input events; multiple synchronous exports can still temporarily block the Painter UI.

For opt-in diagnostics, set `MBTOOLKIT_FONT_DIAGNOSTICS=1` before running Painter (or set it in its Python
process). Under Qt application-local data, `MBToolkit_3DPainter/generated` retains `last-fit-coverage.png`,
`last-fit-probe.png`, `last-fit-overlap.png`, and `last-fit.json`. The overlap preview shows paint in green,
text in red, and their overlap in yellow. JSON and the Python log report layer/stack identity, paint and
probe bounds, scale/seed, requested/read-back offsets, exported PNG SHA-256, final overlap and outcome.
Images from the previous attempt are cleared when a diagnostic Fit starts; an early failure may produce
only JSON. Each calibration is capped at 32 observations, with four attempts maximum. Nested UV fields are explicitly written back to
support copy-on-get bindings. Identical exports alone cannot distinguish a stale host render from mesh
clipping or another unresponsive context. Overlap is measured in exported UV pixels, not a guarantee of
correct appearance on every mesh. No blocking sleeps or guessed-placement fallback are used. Diagnostic
images may contain artwork; they are local, opt-in, and never uploaded automatically.

### Release ZIP

Run `py -3 scripts/build_release.py <output.zip>` (or the equivalent `python` command on your system). The archive always installs one **MBToolkit_3DPainter** directory; a version suffix is allowed on the ZIP filename only. Do not rename the extracted plugin folder. The builder excludes tests, caches and repository internals. GitHub source archives are not the installable release artifact.

Select a text paint layer (or its text mask Fill effect) to edit it. **Live update** is enabled by default:
text, font, relative size, alignment and spacing apply after a 250 ms pause. Relative size also
updates while dragging its slider. Turn **Live update** off to use **Update text** manually; the button
also applies pending edits immediately. Pending edits are canceled when selection changes or the tool
is unloaded. Empty text is skipped during live editing, and live failures appear in the status label
(hover for details); use **Update text** to retry with error reporting. Font search/refresh and loading
a selected mask do not write changes back to Painter. Viewport behavior still needs in-Painter testing.

The **Size (0 = auto)** slider and number field range from **−1 to +1**: −1 is 25%, zero is native auto-size,
and +1 is 400%. The source stays auto-sized as text/font/spacing change; relative adjustment is applied
to its UV Tiling scale, preserving rotation, mirror signs and offset. Repeated edits are relative to a
stored baseline, not cumulative. The **0** button restores the baseline. Per-mask size/baseline values
are saved in Painter project metadata so they survive plugin reload and project reopen. Untracked older
masks adopt their current projection as baseline; editing them enables native auto-size. UV projection
with valid Tiling factors is required. Enlarging can exceed existing paint coverage; this never moves paint.

Select a text paint layer (or its text mask Fill effect) to use the **Rotation** slider/degree field,
**Flip horizontal**, and **Flip vertical**. These apply immediately to the selected UV-projected mask,
preserving its offset and scale magnitude. Slider changes apply when released. Selecting the mask reads
its existing rotation; clicking a flip button twice restores that axis. Flip requires Tiling scale mode.
Signed rotation is normalized to a nonnegative equivalent for Painter (for example, -30° is written as 330°).
Other projection modes are left unchanged and show a message. These controls affect the mask, not paint content.
The rotation row uses the Channel Blending slider style. Its reset button restores the projection saved
before this panel session's first rotation/flip edit. Without a saved snapshot it clears rotation and
negative scale signs while keeping position and scale magnitude. Failed transform writes attempt rollback.
If text has already disappeared, resetting cannot guarantee recovery: the mask may be outside existing
paint coverage, and an earlier projection is only available through Painter undo or a saved session snapshot.

## Development / tests

```sh
python -m pip install pytest ruff
python -m pytest -q
python -m compileall -q painter_python/plugins/MBToolkit_3DPainter
ruff check painter_python/plugins/MBToolkit_3DPainter tests
```

The runtime depends only on the Python, PySide6 and `substance_painter` APIs bundled in Painter; **do not** `pip install substance_painter`.

See [ARCHITECTURE](docs/ARCHITECTURE.md), [COMPATIBILITY](docs/COMPATIBILITY.md) and [MANUAL_TESTS](docs/MANUAL_TESTS.md).

## Official API references

- [Plugin loading and lifecycle](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/writing-plugins/substance-painter-plugins)
- [User UI API](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/ui)
- [Layer blending editor example](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/examples/blending-mode)
- [Layer navigation](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/navigation)
- [Font API](https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/source-module/font)

## License

MIT, © 2026 Marius Brill. See [LICENSE](LICENSE).
