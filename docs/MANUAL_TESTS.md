# Manual Painter test checklist (mandatory before a release)

Capture Painter version (`application.version_info()`), OS, GPU, and any Qt/Python console errors.

- [ ] Painter discovers package via `SUBSTANCE_PAINTER_PLUGINS_PATH` (repository moved to a different directory).
- [ ] MBToolkit top menu present exactly once and preference window opens.
- [ ] All three features turn off/on independently, keeping the menu available.
- [ ] Toggle features, reload plugin five times; no duplicate menus, shortcuts, events, docks or crashes.
- [ ] Settings survive restart, import/export works, malformed/newer-schema settings do not silently overwrite.
- [ ] Multiple pies, shortcuts, 1–12 actions, cursor-near-screen-border, high DPI, multi-monitor, Escape, missing action.
- [ ] Native Fill/Paint/Group commands work when project open and fail gracefully when closed.
- [ ] Custom Python scripts default disabled, require confirmation, only run from user config/scripts when enabled.
- [ ] Blend dock shows all relevant channels for paint/fill; blend/opacity remain after switching layers and undo/redo.
- [ ] Rapid opacity drag stays interactive and doesn't reset on every painter model event.
- [ ] Numeric opacity and sliders stay synchronized; typing is not overwritten by model events, and switching selection never edits the previous layer.
- [ ] Apply to all skips unavailable channels, shows Mixed/— for differing values, and never writes on refresh. Resets explicitly set Normal and 100%, not channel-specific creation defaults; footer presets change blend mode only.
- [ ] Blend panel remains readable at narrow/wide dock sizes and high DPI; unsupported channels are disabled with explanatory tooltips.
- [ ] Blend panel disabled for no project / unsupported node / multiple selected.
- [ ] Older settings/imports discard the removed inspector toggle and pie command while preserving other preferences.
- [ ] Font resource list includes Painter fonts; Create paintable text inserts a paint layer with a black mask and white-on-opaque-black SourceFont Fill effect; layer content is selected, not the mask.
- [ ] Paint broad colored/material strokes on the content; only lettering is visible. Load the selected layer, change text/font/size/alignment/spacing, and update: existing paint is revealed by the new lettering, not replaced. Previously unpainted areas remain empty.
- [ ] Position the text mask Fill effect using projection controls; text/font updates preserve the projection. Load/update also work with the mask Fill effect selected; content effects, non-font selections and legacy Base Color text fills show an error.
- [ ] Save/reopen the project; text mask remains editable. Undo/redo creation and updates. With multiple font mask effects, selecting the layer reports ambiguity; selecting a specific effect edits only that effect.
- [ ] Confirm copied plugin contains no hard-coded user paths and works in read-only application installs.
- [ ] Test each Painter major/minor version to be listed as supported, on each claimed OS.
- [ ] Leave Preferences open, unload/reload; closing the dialog must not interrupt teardown.
- [ ] Create/duplicate/delete pies and switch between different shortcuts; names and action lists must not be overwritten or duplicated.
- [ ] Attempt font creation with empty/whitespace-only text; show an error without inserting a layer.

**Open risks:** Font SourceFont availability on the earliest target Painter versions; event ordering; QAction conflicts with other plugins; Painter undo integration on rapidly updated sliders.

## Experimental paint-first placement

- [ ] Prepare text area selects the new unmasked paint layer content. Paint an off-center patch, Fit, and verify the text is centered on the patch (not the UV tile), with correct scale and no repeated lettering.
- [ ] Verify both U and V placement using patches in opposite corners. Confirm exported Base Color alpha actually represents isolated paint coverage in the installed Painter version.
- [ ] Layer visibility is unchanged after success, cancellation, and export failure; the temporary export directory is removed. Existing paint is never deleted.
- [ ] Empty paint, fully opaque coverage, existing mask, grouped paint, multiple UV tiles and layered materials are rejected clearly without modifying paint/masks.
- [ ] Change text/font after fitting: placement and paint remain intact. Test save/reopen and undo/redo. Compare 2D UV placement with 3D appearance across seams; do not treat the result as a 3D surface centroid.
