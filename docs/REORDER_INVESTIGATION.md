# Automatic reorder investigation — October 26, 2026

## Follow-up: command experiment and partial prototype

The following later tests supersede the initial read-only scope below. Copied the
bundled fixture to the temporary directory as `MBToolkit_Reorder_Command_Test.spp`.
Only this disposable copy was mutated; neither project file was saved.

- **Layer cut/paste rejected in the tested environment:** Cut removed UID 109;
  the clipboard subsequently had no formats and Paste remained disabled. Native
  Undo restored the exact original root order and UID. This does not establish
  whether the failure was clipboard/environment-specific, and no identity claim
  about a successful paste is possible. It is not a viable backend on this evidence.
- **Effect commands viable for a limited prototype:** three content Levels effects
  moved to the top with unchanged UIDs; native Undo/Redo restored exact orders.
  The actual prototype also moved an effect in that content stack successfully.
- All four prototype commands (top/up/down/bottom) then passed on five Levels
  effects in a mask on a paint layer nested two groups deep. One effect was hidden;
  node identity/visibility and all scanned hierarchy data were preserved. Each
  command passed exact native Undo/Redo order checks. Duplicate default effect
  names were present and did not affect selection by UID.

Implemented `native_effect_order.py`, integrated into graph port-drop validation
and commit, behind `MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER=1` on Painter 11.0.3.
One effect, one existing content/mask scope, one native action per operation.
Supports adjacent moves and either boundary, not arbitrary interior jumps, batch
moves, layers, reparenting or stacks containing anchors. Requires English native
labels. Disabled by default. This does **not** satisfy universal all-layer reorder.

No cursor movement, clipboard operations or node reconstruction in the prototype.
Every commit checks context and hierarchy again and verifies the expected chains
and scanned node records afterward. Verification failure reports an error; it
does not blindly undo or claim transactional rollback. Shader parameters, strokes
and rendered output are not exhaustively compared by these structural checks.

Live tests used `scripts/painter_command_reorder_test.py` with explicit phases.
Its setup refuses another project or an existing disposable file. A JSON report
is written alongside the disposable project in the temporary directory.

Automated planning/backend tests plus existing ordering tests: **31 passed**.
Other effect families, anchors, instances, rendered output and other host versions
remain unverified. The old cursor-based layer experiment remains separate.

## Scope and actual live observations

Inspected Windows Painter 11.0.3 through its explicitly enabled localhost remote
scripting server. No project was open initially. Loaded Adobe's bundled
`resources/python/modules/automated_tests/resources/layerstack-cube.spp` without
saving it. No move, paste, cut, selection setter or action trigger was executed.

The fixture contained four root layers and nested groups. Its effect stacks were
empty despite one layer's descriptive name. Therefore populated effect behavior,
instances, anchors, Undo/Redo and identity preservation are **not validated**.

## Findings

- Both `Alg::LayersStackView::Impl_` and `Alg::ActionsStackView::Impl_` advertised
  only `CopyAction` and `application/x-qabstractitemmodeldatalist`.
- Root model rows had only `ItemIsEnabled`, no drag/drop flags; DisplayRole was
  empty. Advertised roles were Qt's six default roles. Internal IDs were pointer-
  sized values, not Painter node UIDs. Do not interpret them as stable identities.
- No move slot was exposed on the inspected layer/effect panel metaobjects.
- Inspection of installed `_substance_painter.layerstack` names found no move or
  paste entry point. This is a negative observation, not permission to call private APIs.
- **Important:** QObject child traversal missed native actions attached to widgets
  but owned elsewhere. `QWidget.actions(layer_panel)` revealed unnamed actions:
  - Move effect(s) to top / up / down / to bottom (disabled in this fixture).
  - Cut layer(s), Paste layer(s), Paste layer as instance, Paste into content.
- No layer-up/down action was found in that attached-action list. This does not
  prove that no such action can exist in another context or version.

The generic model-MIME route is not a demonstrated move backend. The native
application uses custom drag/drop handling; standard Qt method availability alone
does not prove an identity-preserving move implementation.

## Next automatic candidates

1. **Effects: attached native ordering actions.** In a disposable project, select
   effects through the public API and verify enabled actions, exact sibling order,
   UID preservation, content/mask behavior and Undo/Redo. Resolve actions at use
   time; names are empty, so the existing uniquely named action catalog excludes
   them. Label matching is localized and version-dependent, not a public contract.
2. **Layers: native cut/paste.** Investigate only on a disposable copy. First prove
   the clipboard protocol preserves the same native nodes and all references.
   Test cancellation and failure between cut and paste, not only the happy path.
   Clipboard replacement and temporary deletion are risks, not accepted behavior.
3. If cut/paste changes identity, reject it. Native drag/drop delegation remains a
   separate unsupported research path; do not fabricate MIME payloads or call C++
   addresses. Do not substitute another timed cursor simulation.

These may require separate effect and layer backends behind the existing pure
MovePlan interface. One universal backend has **not** been established.

## Acceptance gate

Test Fill, Paint, Instance, Group, nested and collapsed groups, duplicate labels,
all content/mask effect families, hidden/disabled nodes, anchor consumers, and
mixed selections supported by Painter. Require exact UID/subtree preservation,
correct target scope/order, preserved parameters/strokes/references, expected
render changes, and exact native Undo/Redo. Verify project/stack changes and
failures do not leave a partially applied operation. Native anchor order changes
can alter reference eligibility even when UIDs survive.

## Repeatable diagnostic

Run `scripts/painter_reorder_probe.py` inside Painter. For JSON over the existing
remote helper, evaluate `runpy.run_path(absolute_probe_path)["report"]`.
The probe reads metadata only and compares hierarchy, dirty state and selection
before/after. The first successful populated run reported all three unchanged,
with `needs_saving()` false before and after. It does not call `mimeData`, move or
drop operations or trigger actions. It does not serialize material parameters.

Production reorder behavior and opt-in gates are unchanged. Existing pure ordering
and connection tests: 24 passed. This does not establish native move reliability.