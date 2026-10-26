# Anchor Manager — implementation and validation

## Enable and open

1. Install/reload the existing MBToolkit plugin as described in the root README. Do not enable two copies.
2. Open **MBToolkit → Preferences → Features → Anchor Manager**. This optional feature defaults **off**.
3. Open **MBToolkit → Anchor Manager** to show/hide its dock. The command `mb.anchors` is also available to pies.
4. Open an editable Painter project. The active texture set/stack is authoritative; the selector changes Painter's active stack.
5. Search by anchor, path or consumer. Select an anchor for its textual consumers, then select a consumer/input for reference details. Double-click rows/cards to navigate in Painter.
6. Use Focus/Overview/Issues graph modes or **Expand Graph**. Wheel zooms; background dragging pans; F centers the selected card. Graph operations never move Painter layers.

Use **Refresh** to retry a failed scan. **Copy diagnostic** includes capability explanations, host version, coverage and counts; review project labels before sharing. It does not intentionally collect project filenames, user directory names or session UIDs. Windows paths in exception text are redacted.

## Architecture

The canonical runtime package contains `features/anchor_manager/`:

- `models.py`: pure typed, ephemeral project/stack/node and input identities.
- `index.py`: reverse usage, search/filter/sort, conservative issues, deterministic two-lane layout.
- `capabilities.py`: explicit supported/read-only/partial/unsupported gates and explanations.
- `painter_adapter.py`: all host access, public API probes, object resolution, source metadata and mutations.
- `discovery.py`: iterative hierarchy traversal and recursive procedural image-input discovery.
- `operations.py`: immutable preview targets, fresh preflight, commit and authoritative reread.
- `controller.py`: main-thread bounded scan pumping, 350 ms refresh coalescing, context invalidation, shared selection.
- `ui/`: native Qt list, inspector, per-input graph edges, impact dialogs and responsive dock.
- `feature.py`: existing `DockFeature` integration. No second menu or plugin bootstrap.

Host APIs are never called from worker threads. Discovery yields between nodes/source inputs with an approximately 8 ms pump budget; an individual host call cannot be preempted. Mutation preflight/reread currently perform synchronous full scans, so edits on exceptionally large documents can pause. No responsiveness guarantee has been measured inside Painter.

User settings preserve filter, sort, auto-refresh, graph mode/zoom, splitter sizes and expanded-window geometry through existing toolkit settings. Session node IDs, selection and cached graph identities are never persisted. Painter manages the dock's own geometry.

## Capability matrix (2026-10-24)

Installed files inspected: **Painter 11.0.3**, API **0.3.4**, Python **3.11**, PySide6. This is static inspection, not a successful interactive host test. Official online documentation may describe a newer API; runtime capabilities, not that version number, control behavior.

| Operation | Implemented state | Gate / limitation |
|---|---|---|
| Recursive anchors, groups, content/mask paths | Supported when public methods available | Unreadable branches become coverage gaps, not empty branches |
| Material fill source | Supported read; restricted write | `source_mode`, `get_material_source`, `SourceReference` |
| Split fill channel sources | Supported read; restricted write | Enumerates stack channels, including disabled channel assignments where readable |
| Mono mask fill sources | Supported read; restricted write | `get_source(None)` / `set_source(None, anchor)` |
| Procedural image inputs | Partial, read-only | Recurses `SourceSubstance.image_inputs` and `get_source(identifier)`; other parameter categories remain unverified |
| Paint/instance embedded inputs | Partial / unscanned | Usage totals remain lower bounds |
| Create | Capability-gated | Selected layer content/mask or above selected effect; eligible selection and path rechecked |
| Rename | Capability-gated | `Node.set_name`; trimmed nonempty name, duplicate-label warning |
| Native navigation | Capability-gated | `get_node_by_uid`, `set_selected_nodes`; never inside mutation scope |
| Replace one / replace all | Partial | Only direct fill references to anchors in the same chain with an anchor-only interval; all other candidates disabled with explanation |
| Preserve reference settings | Required before replacement | Snapshot/reapply channel mapping or referenced channel, levels and alpha matte; unreadable settings gate editing |
| Delete | Capability-gated, conservative | Only completely scanned zero-use anchors, confirmation, fresh preflight |
| Undo batches | Supported if available | `ScopedModification`; exceptions may leave partial changes, not atomic rollback |
| Disconnect | Unsupported / disabled | Reset/default-source semantics not host-validated; use native Painter properties |
| Anchor output thumbnail | Unsupported | Honest placeholder; no screenshots or export hacks |
| Exact nested ordering validation | Unknown outside restricted cases | No fabricated ordering errors or automatic fixes |

The surrounding toolkit targets Painter **10.1+ / PySide6**. Qt5/10.0 and earlier remain outside the existing bootstrap's supported range; no broad Qt5 rewrite was made. 10.1-era builds and later releases require runtime probes and the smoke checks below before being called supported. No tested-host compatibility claim is made for any version by this delivery.

Official references consulted (and checked against installed public wrappers):

- https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/source-module/reference
- https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/source-module/substance
- https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/edition
- https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/selection

## Coverage and safety semantics

- Each actual input slot is a separate edge, even when the same consumer references the same anchor twice.
- “Complete” means all applicable implemented public source categories were enumerated without gaps, not a promise of full-project semantic analysis.
- Any procedural source conservatively introduces a coverage gap for unverified non-image parameters. Paint/instance inputs and unknown source types do likewise. Consequently **Unused may be empty on typical complex documents**. This is deliberate, not a zero-use bug.
- A resolved anchor outside the enumerated hierarchy is `SOURCE_NOT_FOUND`/unknown, not confirmed broken. A metadata read exception is unknown. Only an explicit dangling `SourceReference.anchor is None` produces confirmed broken state.
- Total counts show known edges, never inferred complete usage when coverage is partial.
- Replacement candidates are intentionally narrower than Painter's native picker: same owner, same content/mask domain, and no intervening non-anchor effects. This preserves the source's stack/channel context without pretending to prove arbitrary nested ordering.
- Confirming a modal does not trust the current Manager selection. It retains its original index/slot identities and rereads the host, rejecting changed bindings, reference settings, disappeared targets and changed paths/types/names.
- UID reuse with identical metadata in the same session cannot be distinguished without a stronger host identity contract. No persistence guarantee is assumed. Close/open lifecycle events replace the session token.
- Failure after a setter or settings restoration can leave partial host edits. The report says so; inspect Painter and Undo. No optimistic graph connection is committed.

## Automated checks

From the repository root on this Windows development machine:

```powershell
py -3.13 -B -m pytest -q -p no:cacheprovider
py -3.13 -m ruff check --no-cache painter_python/plugins/MBToolkit_3DPainter tests
py -3.13 -m compileall -q painter_python/plugins/MBToolkit_3DPainter
```

Tests use a fake public Painter surface with the real adapter. They cover nested traversal, mask/content domains, duplicate names, per-channel edges, procedural inputs, partial/unknown/broken distinctions, rename/search, session invalidation, preflight, preserved settings, batch failure, safe deletion, incremental cancellation and deterministic 100-anchor/500-edge layout. An isolated real offscreen Qt subprocess exercises the dock, inspector, graph, replacement dialog, debounce, empty/error states, and teardown. Existing toolkit regressions also run.

### Recorded local validation — October 24, 2026

- Full pytest suite: **241 passed in 22.00 seconds**, no skips/failures in the recorded final run.
- Ruff: **All checks passed**.
- Runtime compileall completed without reported syntax errors; all **47 runtime Python files** additionally parsed with Python 3.11 grammar using `ast.parse(feature_version=(3, 11))`.
- Release ZIP built in the OS temporary directory; archive integrity check passed, Anchor Manager runtime and this document are included, and Python bytecode caches are excluded.
- `git diff --check`: no whitespace errors (only existing Git line-ending conversion warnings).
- Painter was not launched or controlled interactively. No M1–M4 host acceptance is claimed.

## In-Painter smoke checklist — REQUIRED, not executed by the coding agent

Record Painter version, API version, OS, project fixture, result and diagnostic for each test. Test installed 11.0.3 first, then oldest targeted and a middle build if available. Do not mark M1–M4 fully accepted until relevant checks pass.

- [ ] Enable/disable/re-enable Anchor Manager; verify exactly one MBToolkit menu, no duplicate docks/callbacks, and other features still work.
- [ ] No project, project loading, edition-left/busy state, project close and rapid project replacement: no stale rows/actions/crashes.
- [ ] Two texture sets and material stacks: selector and native switching clear old selection and load the correct anchors. Repeat with auto-refresh off and manual Refresh.
- [ ] Nested groups; content and mask anchors; anchors above/below effects; duplicate labels: verify exact paths and independent identities.
- [ ] Mono mask, split channel and material fill consumers: compare every slot and mapping against native properties. Include disabled channels and the same anchor in two inputs.
- [ ] Generator/filter procedural image inputs: compare exposed inputs, known counts and partial coverage with native UI. Verify no unsupported input gets classified unused.
- [ ] Search names/paths/consumer names; each sort; Used/Unused/Issues; selected-layer scope. Unused excludes all partial scans.
- [ ] List/card double-click navigates to native anchor/consumer; single click only updates Manager. Reference Details shows precise slot/channel/mapping.
- [ ] Graph Focus/Overview/Issues, Fit, zoom clamp, keyboard F, expanded graph, narrow dock, HiDPI. Confirm per-slot edges have separate tooltips and selection.
- [ ] Create in content, existing mask and relative to effect; no selection; invalid selection; empty name; Cancel. Confirm no ghost anchor after failure.
- [ ] Rename, duplicate-name confirmation, Cancel, external native rename during modal, Undo/Redo and search refresh.
- [ ] Two adjacent anchors in one chain: replace mono, split and material references separately. Verify levels, source channel/mapping, alpha matte and unrelated parameters survive. Confirm both scope and undo history.
- [ ] Cross-set, different-chain and intervening-effect candidates disabled with a reason. Procedural edits and Disconnect disabled.
- [ ] Replace-all preview includes skipped/unknown entries, only checked eligible slots mutate, grouped undo where available, honest partial-failure report.
- [ ] Change consumer binding/settings or delete source/consumer while a modal is open: confirmation rejects stale preview and reindexes.
- [ ] Completely scanned fill-only fixture with an unused anchor: delete confirmation and Cancel, deletion and Undo. Used/partial anchors cannot be deleted.
- [ ] Native insert/delete/relink/rename and Undo/Redo refresh; event bursts coalesce; hidden manager does not perform deep scans.
- [ ] At least 100 anchors/500 edges: measure indexing and graph navigation; verify bounded overview banner and usable Focus/textual workflow.
- [ ] Copy diagnostic and review for personal paths; close/reload plugin with expanded window open and confirm cleanup.

## Explicit deferred scope

Not delivered: broad arbitrary relinking, procedural input editing, disconnect, thumbnail rendering, transitive graph exploration, drag-connect, movable graph cards, full selected-group descendant scope, multi-select/bulk rename/delete, CSV/JSON inventory export, progressive cluster expansion, persisted column visibility, and a graph-independent compact reference-tree tab. The textual library/consumer inspector remains usable without graph interaction. Responsive layout uses vertical sections below 750 px rather than reproducing every wide/medium mockup detail.

Implemented M1/M2/M3 subsets are locally tested; **none is declared fully accepted in Painter**. Broader capabilities should be added only after public API and host smoke verification.