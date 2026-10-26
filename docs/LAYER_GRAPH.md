# Layer Graph — experimental node-first workspace

## Enable

1. Reload the existing MBToolkit plugin; do not enable a second copy.
2. Enable **MBToolkit → Preferences → Features → Layer Graph (Prototype)** (off by default).
3. Open **MBToolkit → Layer Graph (Prototype)**. The command `mb.layer_graph` is available to pies.
4. Open an editable project. The graph follows Painter's active texture set / material stack.

This is a working editing prototype, **not a complete replacement for Painter's native layer editor**.
It creates real Painter layers, groups, masks and effects; Painter remains the evaluator.
Keep the native Properties panel available for brush painting, fill sources, projections, generator/filter
parameters, ID picking and other specialized editors. Single-click a node, or Shift + right-click → **Select in Painter / Native Properties**
targets the exact native layer/effect. Changing the graph layout never changes rendering.

## Interaction

- Right-click opens the searchable add-node popup immediately; **Tab** and **Space** also open it.
  Type to filter, then single-click a row or press Enter to insert. Up/Down navigates; Escape or clicking
  outside dismisses. Only available entries appear, with plain names and no category prefixes.
- Generator, Filter, Bitmap Mask and smart presets switch to a resource list **inside the same popup**.
  Backspace on an empty resource search returns to node types. No separate Add button or resource window.
- **Shift + right-click** opens management commands; **F2** renames a selected node.
- Add above a selected node, or at the top of the current graph scope when none is selected.
- Drag nodes to arrange them; wheel zooms; middle-button drag pans; box-drag selects; **F** focuses selection
  or fits the graph. Shift + right-click **Fit Graph**, **100%** and **Refresh** are also available.
- Movement is free: nodes do not auto-align during a drag or on release. Ordinary refreshes wait until
  the gesture ends, and saved positions (including inline nodes and input/output cards) survive refresh.
  Use **Arrange by Evaluation Order (Layout Only)** explicitly to reset placement. Project/stack changes
  cancel active gestures and reset the session layout as usual.
- The main graph is a bundled multichannel material stream. Wires show Painter's bottom-to-top evaluation
  order as left-to-right flow; cards' screen positions do not determine that order.
- Input/output cards have a solid blue body and only the applicable port. Mask backgrounds also have a mask glyph.
  The graph canvas uses the supplied Substance-gray background (`#333333`).
- Drag a port or wire onto empty canvas to disconnect/bypass its real node without deleting it.
  Reconnect to the compatible neighboring port to restore its previous visibility (including intentionally disabled nodes).
  Green/red port highlights indicate valid/invalid targets; **Escape** cancels without a host change.
  Disconnect markers are session-only; the native visibility change persists in Painter. Native enable overrides the marker.
  **Experimental connection reordering is disabled by default because repeated live testing was unreliable.**
  A separate **effect-only native-command prototype** is available with
  `MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER=1` on Painter 11.0.3 (English UI).
  It moves one effect within its existing content/mask stack via native actions,
  without moving the cursor: adjacent moves or either stack boundary only.
  Anchors, layer moves, reparenting and arbitrary interior jumps are rejected.
  Live Levels-effect tests covered content and a nested layer's mask, preserving
  UIDs and exact Undo/Redo order. Other effect families remain unverified.
  See `REORDER_INVESTIGATION.md` for findings, including the failed cut/paste test.
  For development tests only, explicitly set `MBTOOLKIT_EXPERIMENTAL_REORDER=1` in Painter's process environment
  before launching Windows Painter **11.0.3**. It is not recommended for production. When opted in, drag a node's output onto
  another node's input to insert it immediately before that node in evaluation order; drag its input onto
  another output to insert it immediately after. Input/output boundary drops move to evaluation start/end.
  Painter's Layers panel must be visible, with the root rows on screen and uniquely named. This first version
  requires a root stack containing only Fill/Paint layers, without folders, instances or anchor points.
  It briefly drives the real native mouse drag (about 0.6 seconds); do not move the mouse during that operation.
  It preserves the original nodes, reads the resulting hierarchy back, and reports an error on any mismatch.
  Unsupported drops remain rejected, not drawn as fictional dataflow. Native Undo/Redo applies.
  **Shift + right-click → Evaluation Order → Select in Painter to Reorder…** selects the existing native
  node and explains the workflow. Direct move commands remain disabled until a public native move backend
  is verified. The connection-only experimental UI bridge is separate from those public-backend capabilities.
  No delete/recreate or clipboard fallback is used; the UI bridge relies on version-specific native widget structure.
  Keep anchor sources below their consumers when changing native order.
- **Shift + right-click → Arrange by Evaluation Order (Layout Only)** resets positions in this graph
  view to native evaluation order. Other tabs, frames, expanded state, selection and zoom are preserved;
  this never moves a native layer or creates a Painter history entry.
- With multiple native cards selected, **Evaluation Order → Select All in Painter to Reorder…** hands
  off a same-scope selection in native order. Selected descendants of selected groups are omitted.
  Mixed-scope handoff is refused before changing native selection.
- **Alt + click** a mask strip/background invokes a uniquely exposed native mask-preview action when available.
  Hosts without that action show an explicit notice; use Alt + click on the native Layers mask thumbnail instead.
- Click the **eye at the top left** to enable/bypass a real layer or effect in Painter. Bypassed cards
  stay editable but become darker gray with a neutral outline and crossed-out eye; content is preserved.
- Every native card has a type-specific vector icon (brush, fill, folder, anchor, levels, etc.).
  Hovering a node subtly lightens its body and outline; selection and bypass styling remain distinct.
  Single-click its body to select it in Painter and update native Properties; click its mask strip to
  select the mask. Selection does not enter a graph. Masked layers have a separate right-hand mask strip; hover it
  for a lighter-blue highlight, then double-click to enter the mask. Double-click the main body to enter
  content effects (or child layers for a folder). Eye/arrow clicks do not drag or enter the node.
- The **bottom-left arrow** expands/collapses available branches. Empty non-folder layers with no mask
  or effects have no active disclosure control.
- Shift + right-click a node → **Channel Blending…** opens a contextual dialog instead of a permanent inspector.
  Opacity is applied explicitly rather than generating history entries for every spinner tick.
- **Delete** removes the selected real nodes after one confirmation; selected descendants of a selected
  group are not deleted twice. Deleting a selected frame only removes its visual organization, retaining
  native nodes. Input/output cards are ignored. Rename and deletion are also available in the context menu.
- The workspace contains only graph tabs and the canvas: no toolbar, breadcrumb, sidebar, or persistent
  instruction/status rows. Errors and important feedback appear as temporary in-canvas notifications.

## Masks and effects

Each layer owns independent **Content Effects** and **Mask** scopes. Black/White Mask adds an actual mask,
not a disconnected graph object. Bitmap, Color Selection and Height Combination Mask create a black mask
with the corresponding fill/color-selection/compare-mask effect. Existing masks are never replaced.

Right-click a layer body to add to its **Content Effects**, or its mask strip to add to its **Mask Effects**.
Fill and paint creation there uses **Fill Effect** and **Paint Effect**, not material layers.
Expanded content/mask frame backgrounds and input/output cards target their own scope, including nested
branches. Right-clicking an existing effect inserts relative to it in the same chain. The same targeting
applies to **Shift + right-click → Add Node…**. Empty main-graph background still creates material layers.

Double-click a layer body/mask, or Shift + right-click → **Open Mask in New Tab** / **Open Content Effects in New Tab**. The mask graph starts
with its explicit black/white background, then its grayscale effects, then Mask Output. Compare Mask,
Color Selection and Smart Mask are restricted to mask scope. Resource pickers do not silently substitute
empty generators or filters if a resource is unavailable or the user cancels.

The **bottom-left disclosure arrow** opens labeled subgraph frames below the parent, or hides them
without deleting anything. Each frame contains explicit **Input → internal nodes → Output** cards arranged
left-to-right in Painter evaluation order, with separate child-layer, content-effect and mask sections.
Sections attach directly below the parent, share aligned columns and equal widths, and stack without gaps.
Opening another dropdown closes unrelated expansions; nested dropdowns retain only their ancestor path.
Empty folders and masks still show their input/output. Nested expansions stay inside their enclosing frame,
and frames automatically resize when their nodes move. Moving an expanded parent carries its displayed
descendants and frames. The parent's material-stream connections are unchanged. Expanded branches are previews/edit targets; opening their own tab gives
the clearest focused workflow. Right-clicking an inline child uses that child's actual insertion scope.

## Groups, frames and tabs

- **Material Group / Folder** creates a real Painter folder. Double-click or **Open Group in New Tab**
  opens its child-layer graph. Create new layers there to populate the folder. The parent view keeps a
  single group card; use its bottom-left arrow for an inline view. Group masks and content effects have separate tabs.
- **Graph Frame** is visual organization only. Select consecutive nodes in one scope, then **Frame Selection**
  or **Frame Selected Nodes…**. A node belongs to at most one frame. Drag an expanded frame to move its
  nodes together. Double-click its background to collapse, or its collapsed card to expand.
- Rename/collapse/remove frames through their context menu. Removing a frame keeps every native node.
- Frames require consecutive chain members so collapse cannot invent composition order. A native edit
  inserting an unrelated node inside a collapsed frame expands it automatically.
- Tabs share the same underlying Painter data, with independent canvas zoom/pan/selection. Opening a scope
  twice focuses its existing tab. The root cannot be closed. Deleting a group closes its descendant tabs.

## Catalog / implemented public API mapping

| Catalog | Painter operation |
|---|---|
| Paint / Fill Layer | `insert_paint` / `insert_fill` in a material stack |
| Instance Layer | `instantiate` using the selected non-folder layer |
| Material Group / Folder | `insert_group`; child layers use `NodeStack.Substack` |
| Black / White Mask | `LayerNode.add_mask` with explicit background |
| Bitmap Mask | New black mask + Fill effect + selected texture source |
| Color Selection / Height Combination Mask | New black mask + Color Selection / Compare Mask effect |
| Paint / Fill Effect | `insert_paint` / `insert_fill` in content/mask stack |
| Generator / Filter | Resource-backed `insert_generator_effect` / `insert_filter_effect` |
| Levels / Compare Mask / Color Selection / Anchor Point | Corresponding public `insert_*_effect` |
| Smart Material / Smart Mask | Resource-backed `insert_smart_material` / `insert_smart_mask` |
| Graph Frame | Session-only layout; no Painter mutation |

Existing node kinds are scanned and represented even when they are not part of this creation catalog.
Unsupported API methods disable the relevant catalog entry. Native operations still perform final
insertion validation; graph eligibility does not promise every combination is valid in every Painter build.

## Safety, limitations and validation

- **Connection reordering is experimental and narrowly scoped**, not general Blueprint dataflow. The public SDK
  still has no verified move backend. `native_drag.py` bridges port drops to real native UI dragging only on
  Windows Painter 11.0.3 and only for the root Fill/Paint-layer configuration described above. It can move the
  system cursor and depends on native panel layout. Other versions, nested/effect stacks, folders, instances,
  duplicate root names and discovered anchor points are refused. Existing mask/effect contents travel with the layer;
  exhaustive source/reference dependency validation is not established. Test on copies before production use.
  A mismatched readback reports an error rather than silently claiming success; inspect Layers and Undo if needed.
- `ordering.py` implements immutable, host-free plans for same-chain single/batch moves and layer/group
  folder transfers. It uses relative identities and native top-first chains, preserves selected relative
  order, removes selected descendants, rejects cycles/domain transfers/stale hierarchy, and detects no-ops.
  Plans are **not permissions to move**: `Adapter.move()` validates freshly and refuses every non-no-op
  while the public native backend is unverified. Plausible method names do not enable capabilities.
- Dependency preflight requires matching, complete discovery. Anchor/reference-bearing moves remain
  blocked because nested evaluation eligibility has not been host-validated; complete discovery only
  describes scanned public source categories. No persistent dependency cache or project serialization is added.
- Delivery status: pure ordering contracts and non-destructive layout/batch-navigation UI are implemented.
  The experimental connection bridge was run inside Painter 11.0.3 against a temporary copy of PreviewSphere:
  native hierarchy changed as planned, node UIDs were preserved, and native Undo/Redo restored exact orders.
  Production graph port handlers were exercised inside Painter; swapping red/green/blue Fill layers visibly
  changed the rendered sphere from red to green. This does not establish general folder/effect-stack support.
  Repeated live attempts also exposed no-op/mismatched native drops and focus loss when another desktop window
  became active. Those attempts were rejected by readback/focus guards. This is a feasibility prototype, **not a
  reliable production reorder backend**, and successful individual runs must not be interpreted as complete acceptance.
  The public move backend and reorder-grip gesture remain disabled.
- **Layout, frames, expanded branches and tabs are session-only** and reset on project/stack changes.
  They are not yet persisted into project metadata. Material edits are native and are saved with Painter.
- No custom renderer, live material thumbnails, generic procedural parameter editor, reusable Blueprint
  definitions, cross-texture-set wiring, geometry-mask editor, or full native context-menu parity.
- Mutations validate the captured project session and texture stack again before acting. Creation rereads
  the hierarchy; stale/deleted scopes and existing masks are rejected. Bitmap setup failure removes only
  the newly created mask. Mutations are reread, not represented as optimistic ghost cards.
- Multi-call creation/blending uses `ScopedModification` where exposed; this groups undo, not a general
  transaction rollback. Native operation failures are displayed. Use Painter Undo for recovery.
- Refreshes are coalesced while visible; context is polled every second. Timers/listeners are disposed
  on feature shutdown. Modal pickers defer refresh; commits still validate their captured context.
- Connection hover previews read the existing structural snapshot only: no host scan, mutation or second
  hierarchy cache. Reconnection commits reread Painter and reject stale/deleted/moved targets. Project/stack
  changes cancel an active connection gesture before refreshing. Selection after creation occurs outside
  `ScopedModification`, as required by Painter; native undo grouping is preserved.
- Scanning is synchronous on the main thread. Very large stacks can pause the prototype. A failed scan
  clears actionable cards rather than presenting an apparently complete partial hierarchy.

Implementation: `features/layer_graph/model.py` (pure domain/catalog), `adapter.py` (public host access),
`canvas.py` (Qt graphics), `panel.py` (tabs/browser/inspector/lifecycle), `feature.py` (existing dock integration).
The Anchor Manager remains separate and unchanged. Only the new adapter reuses its session/key helpers.

Automated validation exercises the production adapter against a public-SDK double and real offscreen
PySide6 widgets in an isolated process. Those checks alone do not establish native behavior. Additional live
checks above used `scripts/painter_reorder_acceptance.py` (native bridge/UIDs/Undo/Redo) and
`scripts/painter_graph_reorder_test.py` (production graph handlers/render screenshots). Both require the
disposable `MBToolkit_Reorder_Test.spp` project. `scripts/painter_remote.py` sends explicit commands to Painter's
opt-in localhost remote server; remote scripting is needed for test automation, not normal graph operation.

### Host smoke checklist

- [ ] Enable/disable/re-enable; exactly one dock and no surviving callbacks.
- [ ] Open/close/switch projects, texture sets and material stacks; no stale selections/tabs.
- [ ] Create Fill, Paint, Instance and Group; create layers inside nested groups; compare native hierarchy.
- [ ] Add black/white masks; create bitmap/color/height masks; refusal to replace existing masks.
- [ ] Add Generator → Levels in mask scope; compare rendered result and native order.
- [ ] Add all other effect families and presets; cancel resource selection without changes.
- [ ] Rename, visibility, per-channel blending/opacity; native Properties targets correct effect/mask.
- [ ] Independent group/mask tabs, inline collapse, frames, pan/zoom, narrow dock and HiDPI.
- [ ] Native edits and Undo/Redo refresh graph; deletion closes descendant tabs; undo restores native nodes.
- [ ] Change project while a picker is open; commit must reject the stale target.
- [ ] Measure refresh behavior with a large production stack before relying on it as the primary workspace.