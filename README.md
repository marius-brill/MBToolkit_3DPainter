# MBToolkit_3DPainter

**Version:** 0.1.0 (development / unverified in Painter)  
**Maintainer:** Marius Brill  
**Requires:** Adobe Substance 3D Painter 10.1+ (Python 3.11 / PySide6)  
**License:** MIT

A modular toolkit for Adobe Substance 3D Painter, with a dedicated **MBToolkit** top-level menu, individually switchable tools and no hard-coded installation paths.

> **Release status:** This initial package passes host-independent automated checks. The plugin has **not yet been smoke-tested inside Substance 3D Painter**. Painter API and UI integration require validation on the exact installed Painter releases before a production release. Painter 10.1+ is the intended baseline, **not** a tested compatibility guarantee.

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
| Font Tool | Create a paint layer with an editable text mask; edit text, size, alignment, spacing, font without replacing paint | Implemented, host testing pending |

### Feature limitations

- **Text masking, not viewport stamping:** Font Tool uses a procedural `SourceFont` Fill effect in a paint layer's mask. Position that effect using Painter's projection tools. Changing lettering reveals existing paint; it does not move strokes or create paint in previously unpainted areas.
- **Native actions in pies:** Only registered API-backed commands are offered. This first version includes new Fill Layer, Paint Layer and Folder, plus MBToolkit panels. Arbitrary Painter UI commands are not intercepted or scraped by their visible labels.
- **Custom Python:** Scripts run with the current user's permissions, with the same privileges as Painter. Scripts are disabled unless a user explicitly opts in under Preferences.

## Usage

1. Open **MBToolkit → Preferences → Features** to enable or disable tools.
2. Open **MBToolkit → Pie Menus → Manage Pie Menus** to create/reorder wheels, add registered actions, and assign shortcuts. Shortcuts do not have a default value to avoid unknown native conflicts.
3. Open **MBToolkit → Channel Blending** with one paint or fill layer selected.
4. Open **MBToolkit → Font Tool**, choose **Prepare text area**, and paint a broad patch on the layer content. Enter text, choose a font, select the paint layer and click **Fit to painted area**. Existing text masks load automatically when selected; edit and click **Update text**. If a layer has several font mask effects, select the specific effect. Older Base Color text fill layers remain unchanged and are not converted by this workflow.
5. Under **Preferences → Python Actions**, save a local `.py` file and explicitly enable trusted custom actions. Reopen the Pie Menu Editor to assign it.

Settings are stored outside the installation in the OS-specific Painter user configuration directory (via Qt `QStandardPaths`). Use Preferences to export or import portable JSON.

### Experimental paint-first text placement

Choose **Prepare text area**, paint a broad patch on the new layer's content, select that layer,
then choose **Fit text to painted area**. This attaches an editable text mask to the existing paint,
centers a square text source in the patch's UV bounding box with 10% padding, and enables automatic font sizing.
Select the text layer or its mask Fill effect to load settings automatically, then edit and click **Update text**.
Ordinary model events do not reload the same selected mask or overwrite pending text edits.
Disable **Auto fit** to use the logarithmic manual-size slider and precise numeric field; click **Update text** to apply.
Alignment and spacing are under the collapsed **Advanced** section. Help is available in tooltips.

This is UV-space placement, not a 3D viewport center or a guarantee of fitting inside irregular strokes.
Use one continuous patch away from seams and tile edges. The initial implementation only accepts an
unmasked top-level paint layer with Base Color, a single 0–1 UV tile, and no material layering.
It temporarily isolates the layer and exports Base Color alpha at 512px, restores visibility,
and deletes the temporary export. No persistent image cache is created. Empty/full-tile coverage is rejected.
The exported alpha and projection positioning require in-Painter validation before this feature is considered verified.
Fit refuses existing masks rather than overwriting them; it is an initial-placement action, not a repeated refit.

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
