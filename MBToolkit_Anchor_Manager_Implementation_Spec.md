# MBToolkit_3DPainter — Anchor Manager
## Product, UI/UX, Architecture, Implementation, and Validation Specification

**Document status:** implementation handoff / agent-ready specification  
**Project:** MBToolkit_3DPainter  
**Maintainer:** Marius Brill  
**Starting toolkit version:** 0.1.0  
**Module:** Anchor Manager  
**Target host:** Adobe Substance 3D Painter  
**Date:** 2026-10-24  
**Intended audience:** autonomous coding agent working inside an existing VS Code repository.

---

## 0. INSTRUCTIONS TO IMPLEMENTING AGENT (READ FIRST)

You are building the **Anchor Manager** as a modular, optional feature within **MBToolkit_3DPainter**, not as a separate unrelated application. Inspect the existing repository, respect its organization, naming conventions, plugin entry point, packaging, and toggle/disable system. Avoid replacing existing features or rewriting the plugin bootstrap unnecessarily.

The product requirements and behaviors below are authoritative. Exact Painter API accessibility is **not** guaranteed for every requested feature. Before implementing host interactions, consult the installed Painter Python API version and Adobe's official documentation. **Never invent Painter methods or silently claim an unsupported operation succeeded.** For unsupported operations, implement the best functional subset, preserve the complete UI specification as the target, expose disabled actions with an explanation, and report the limitation. The user wants a real plugin, not a static prototype.

Implement iteratively: (1) inspect host/repo and create capability matrix; (2) build data models and a testable graph index; (3) build UI with fixture data; (4) wire read-only host discovery; (5) wire verified edits and navigation; (6) add validation and quality-of-life behavior; (7) test inside Painter, document remaining gaps.

**Non-negotiables:**
- Works without hard-coded paths or user-specific locations.
- Supports Painter releases from approximately the preceding two years when practicable, plus later releases through capability detection and version adapters; do not promise unsupported compatibility.
- Uses supported Painter scripting and Qt APIs. Prefer host-provided Qt binding; account for Qt5/Qt6 variation where relevant.
- Has a single **MBToolkit** top-menu entry; Anchor Manager lives inside that menu and can be independently enabled/disabled in toolkit preferences.
- Its panel is dockable if supported. An expanded workspace can be a floating window/dialog.
- The host project/layer stack is the **source of truth**. The graph is a visualization/editor of actual Painter connections, not a substitute material graph.
- No destructive edit without clear scope, impact preview, and a way to cancel.
- All host write actions should participate in Painter history/undo where supported; group batches into one logical undo transaction when supported.
- UI remains responsive on large documents. Slow/partial indexing is surfaced clearly.
- Tests run without Painter using fixture/fake adapters; in-Painter smoke tests are also documented.
- Never persist cache node UIDs across sessions as guaranteed stable IDs without verifying their persistence contract.

### Definition of done
A user can open the Anchor Manager in Painter, browse all discoverable anchors in the active texture-set stack, find and select an anchor, see its source and referenced consumers, navigate to relevant layers/effects, understand invalid/unavailable references, create/rename anchors where the API supports it, and safely replace/edit connections in cases positively confirmed by the installed host API. The manager does not mislabel unknown relationships as zero-use/valid/broken.

---

## 1. PRODUCT VISION

**One-sentence pitch:** A searchable library and dependency graph for Substance Painter anchors, revealing where each anchor originates, which inputs use it, and how changing it will affect the material.

### Problems being solved
1. Anchors are scattered across content and mask stacks, nested layers, and effects.
2. Following references requires manual navigation between distant stack positions and properties.
3. It is difficult to understand the whole dependency network of a complex asset.
4. Replacing an anchor source in multiple places can be tedious and error-prone.
5. Missing/invalid references and risky ordering changes can be difficult to diagnose.
6. Unused anchors contribute noise and are inconvenient to audit.
7. Artists need faster ways to create, rename, navigate, audit, and maintain anchors.

### Product principles
- **List first, graph on demand.** Most interactions are quick lookups; the graph is for analyzing complex relationships.
- **Contextual information, minimal friction.** Search, find source, find uses, and replace are at most two intentional actions after selecting an anchor.
- **Transparent and safe.** Always distinguish *confirmed*, *suspected*, *unknown*, and *unsupported*.
- **Visual scale.** Large projects must not become unreadable tangles or freeze the interface.
- **Host-native aesthetics.** Dark charcoal background, subtle surfaces, concise typography, restrained blue/cyan selection accents, amber warnings, red only for genuinely destructive/error states.
- **Native organization.** Respect texture sets, layer hierarchy, mask/content stacks, effect order, source channels, and limitations on allowable connections.

### Out of scope
- Replacing Painter's material composition/layer editor with a general node graph.
- Arbitrary cross-texture-set anchor links (unsupported by Painter).
- Bypassing Painter's layer ordering/evaluation rules.
- Changing Painter's internals by undocumented memory manipulation.
- Automatic fix of all broken connections with guessed replacements.
- Heavy real-time image rendering or mandatory thumbnails.

---

## 2. FACTS, ASSUMPTIONS, AND CAPABILITY GATES

### Host behavior to respect
- Anchor point effects expose layer-stack content for reuse elsewhere in their texture-set context.
- Anchor creation is documented via `substance_painter.layerstack.insert_anchor_point_effect(position, name)`.
- Anchors can be inserted inside a layer's content or mask stack or relative to eligible effects.
- A `SourceReference` points at an `AnchorPointEffectNode`; it exposes `.anchor`, and depending on context `.referenced_channel` or `.channel_mapping`.
- Fill effects can set an anchor source (example: `fill_effect.set_source(None, anchor)` for a mono-channel mask context). Fill layers can set a material source (example: `fill_layer.set_material_source(anchor)`).
- Navigation includes `get_root_layer_nodes(stack)`, `content_effects()`, `mask_effects()`, `GroupLayerNode.sub_layers()`, `get_node_by_uid`, `get_parent`, and `set_selected_nodes`.
- Change notifications include `LayerStacksModelDataChanged` and project readiness events such as `ProjectEditionEntered`.
- The official Python API overview was updated in September 2026 (API 0.3.5). Method availability must still be tested in the user's installed build.

### Critical uncertainties (DO NOT OVERSTATE)
- Whether every *generator/filter-specific embedded Substance parameter* that may reference an anchor is inspectable/mutable through the public API.
- Whether all broken/dangling anchors remain queryable as `SourceReference` objects; missing references may appear only as unresolved UI state.
- Whether anchor output thumbnails can be acquired directly for arbitrary nodes.
- Whether a direct signal exists for active-texture-set switching in every supported version.
- Whether every source type can be retargeted without resetting ancillary channel/level settings.
- Whether viewport/source-to-target ordering can be determined reliably in all nested stack/group configurations from the public API alone.

Treat these as **capability gates**. Expose `SUPPORTED`, `READ_ONLY`, `PARTIAL`, `UNSUPPORTED`, and `UNKNOWN` capabilities with explanations rather than pretending these are complete.

### Reference documentation (official)
- Python API overview: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/api-overview
- Anchor points: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/anchorpoint
- SourceReference: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/source-module/reference
- Layer-stack navigation: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/navigation
- Layer-stack editing: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/edition
- Layer-stack selection: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/selection
- Event module: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/event
- Painter plugin creation: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/api-overview

---

## 3. USER PERSONAS AND PRIMARY USER JOURNEYS

**Prop/environment texture artist:** wants to find the anchor driving edge wear on a metal prop and see all downstream uses.

**Material/lookdev artist:** wants to reassign a shared wear mask from one anchor to a cleaner variation without editing five separate fill effects.

**Technical artist:** wants a report of all anchors, broken/unknown connections, unused references, and potential dependency hazards.

**Junior artist:** needs to understand which layers provide inputs to a generator without tracing scattered UI controls.

### UX stories / acceptance intents
1. Open Manager -> select `Vehicle_Body` -> see anchor list and counts. No mandatory initial graph interaction.
2. Type `wear` -> only matching anchors appear; results update as the user types.
3. Select `Paint Wear` -> center graph isolates/directly emphasizes upstream source and its consumers; inspector shows location, type, uses, actions.
4. Double-click `Paint Wear` -> Painter selects or reveals corresponding anchor in the layer stack.
5. Click `Roughness Variation` consumer -> inspector shows input slot, channel mapping, current anchor and navigation options.
6. Choose Replace Reference -> select alternative eligible anchor -> preview impact -> confirm -> inspect updated graph.
7. Switch to `Unused` filter -> find anchors with **confirmed zero uses**, not anchors whose scan is incomplete.
8. Select an unused anchor -> request Delete -> view impact confirmation -> delete only if supported and safe.
9. Enable `Issues` filter -> see confirmed broken references, questionable ordering, duplicate labels, incomplete scans separately.
10. Switch texture set -> list/graph refresh correctly without leaking nodes from the previous set.

---

## 4. INFORMATION ARCHITECTURE / SCREEN STATES

### Entry and window types
- MBToolkit menu: `MBToolkit > Anchor Manager` toggles visibility.
- MBToolkit preferences: `Features > Anchor Manager [on/off]` and optional `Default launch mode`, `Auto refresh`, `Graph zoom`, `Thumbnails`, `UI density`.
- Default **dockable compact/medium workspace**.
- `Expand Graph` button opens a larger floating graph workspace, sharing the same selected anchor and filters.
- Window geometry, splitter positions, column visibility, filter state and zoom persist **per user** via toolkit settings. Project-specific sensitive/unstable identifiers must not be blindly persisted.

### Primary window (wide)
```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ MBToolkit / Anchor Manager   [Texture Set: Vehicle_Body ▼] [Refresh] [+ Create Anchor ▼]  │
├───────────────────────┬───────────────────────────────────────┬────────────────────────────┤
│ ANCHORS (8)           │ ANCHOR GRAPH                          │ ANCHOR DETAILS             │
│ [Search anchors...  ] │ [Overview] [Dependencies] [Focus]   │ Paint Wear                 │
│ [Used][Unused][Issue] │ [Fit] [100%] [+] [-] [Expand]       │ [preview or placeholder]   │
│                       │                                       │ Source path                │
│ ▣ Paint Wear       3  │ [Paint Wear] ─────────>[Edge Wear]   │ Paint Layers > Base > Mask │
│ ▣ Height Details   4  │         ╲                            │ [Go to source]             │
│ ▣ Dirt Mask        2  │          └──────────>[Dirt Overlay]│ USED BY (3)                │
│ ▣ Rust Spread     !2  │ [Height] ───────────>[Roughness]    │ Edge Wear  [Go] [Replace] │
│ ▣ Decal Mask       1  │                                       │ Dirt       [Go] [Replace] │
│ ▣ AO Detail        1  │  dashed amber = issue/uncertain     │ Roughness  [Go] [Replace] │
│ ▣ Edge Damage      1  │                                       │ [Rename] [Delete...]       │
│ ▣ Color Variation  0  │                                       │                            │
├───────────────────────┴───────────────────────────────────────┴────────────────────────────┤
│ [Overview] [Selected Dependencies] [Unused] [Issues]   8 anchors  14 known edges  1 issue │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```
NOTE: This is a **layout concept**, not a literal claim that the counts or sample connections exist in a user's project.

### Main panels
**Left: Anchor Library** — continuously searchable anchors, source icon, optional mini-thumbnail, usage counter, status glyph, name and concise origin. Width about 22–27% in a wide window; 280px preferred floor subject to responsive collapse.

**Center: Dependency Graph** — primary canvas, about 50–55% width, with grid, pan/zoom, fit, grouped node lanes, optional selection focus and connection hover interactions. In compact mode center can switch to a hierarchical reference list instead.

**Right: Inspector** — about 24–30% width, selected anchor or selected consumer; exact source breadcrumb, type, known/unknown usage counts, references, input slots, channel mapping, warning states and safe actions.

**Bottom: Status/filter bar** — current mode, scan status, scanned node count, known anchor count, confirmed connection count, uncertain connection count, issues, and refresh action.

### Responsive states
- Wide (>=~1100px): three columns.
- Medium (~750–1100px): collapsible right inspector, adjustable library width.
- Narrow (<~750px): library plus inspector with Graph tab; never allow text controls to overlap.
- No project: designed empty state `Open a Substance 3D Painter project to inspect anchors.`
- No anchors: `No anchors found in this texture set.` with Create Anchor only where valid selection exists.
- Scanning: non-blocking progress and badge `Indexing…`; known counts labeled `partial` until scan complete.
- Error: explain scan failures and provide `Retry` / `Copy diagnostic` controls.

---

## 5. ANCHOR LIBRARY FEATURES

### Row layout
- Optional 40×40-ish preview tile; when unavailable use a neutral glyph, not arbitrary/misleading pixels.
- Anchor name (editable via F2/context menu).
- Source type hint: `Content`, `Mask`, or `Effect`.
- Source breadcrumb ellipsized with full tooltip.
- Usage count only when discovery is complete: e.g. `3 uses`, `0 uses`; otherwise `≥3 known uses` or `Unknown`.
- Status indicator: no icon for healthy; amber for warnings; red for confirmed invalid connections.
- More menu (`…`) for Navigate, Rename, Copy Source Path, Focus in Graph, Find Uses, Delete.

### Search / filters
- Debounced text search (~120–200ms) against name, layer name, breadcrumb and optional consumer name.
- Case-insensitive; supports substring; no need for complex query grammar in first release.
- Filter chips: `All`, `Used`, `Unused`, `Issues` and optional `Selected Layer` / `Selected Group`.
- Sort: Name, Number of Uses, Stack Order, Source Type. Stable tie ordering.
- A zero-use anchor found during a partial scan is **not** classified unused until all discoverable input slots are scanned.
- `Issues` includes separately labeled `Confirmed Broken`, `Possible Ordering Hazard`, `Duplicate Name`, and `Unscanned/Unsupported Connections`. Do not conflate warning with breakage.

### Batch actions (second milestone)
- Multi-select anchors with Ctrl/Shift.
- Bulk rename with preview; optional `ANC_{type}_{original}` preset and collision protection.
- Bulk delete only anchors confirmed unused and with user confirmation.
- Export inventory as JSON/CSV if simple and useful; no dependency on cloud integrations.

---

## 6. GRAPH REQUIREMENTS

### Logical model
This is a **directed dependency graph**. Anchor point = producer/source, referencing input slot = consumer. Each edge = *one actual source-reference relationship*, not simply a relationship between two layer names. If one effect uses the same anchor in two slots, represent two separately addressable edges or an explicit combined edge with two slots, with an easy way to disambiguate.

Suggested graph entity layers:
1. **Anchor node**: anchor name, uid, parent breadcrumb, domain (content/mask), preview/status.
2. **Consumer node**: layer/effect name, parent breadcrumb, consumer type.
3. **Input port**: specific source slot, target channel, optional referenced source channel or mapping.
4. **Edge**: source anchor -> consumer input port, with supported/unknown validity, diagnostic and target location.

### Default layout
- Anchor producers on left lane, consumers to right lane; same source groups align together.
- Reuse a consumer node if it has multiple anchor inputs; show distinct input ports/labels.
- Prefer a deterministic layered/DAG layout. Minimize wire crossing by barycenter ordering or similarly lightweight heuristic.
- Auto-layout must not imply a false layer order/evaluation dependency beyond actual references.
- Graph positions are UI state; preserving manually moved positions is optional and only per session unless persistence is safe.
- Provide `Fit to Content`, `Center Selection`, `Reset Layout`, `Zoom In`, `Zoom Out`, and pan by middle mouse or space+drag.
- Scroll wheel zoom centered on cursor; clamp to comfortable range (e.g. 25–250%).
- Drag nodes for visual arrangement only (initially). Moving a graph node must never move a Painter layer.

### Display modes
- **Overview:** all discovered anchors and known consumers in selected texture set. For very large graphs, cluster consumers by parent layer/group and progressively expand.
- **Selected Dependencies / Focus:** chosen anchor + immediate consumers by default. Optional recursively expand transitively where a consumer also hosts another anchor; distinguish direct vs transitive dependencies.
- **Upstream / Downstream:** optional focused relationship exploration; anchor source is itself associated with an originating layer/effect and may depend on inputs.
- **Issues:** show error/warning/unsupported edges and related anchors, filter out unrelated normal nodes.
- **Compact list view:** accessible alternative for small docks and keyboard-only navigation.

### Node visuals and edge semantics
- Source anchor: dark raised rectangular card, cyan icon, concise name and source path, bright cyan outline only when selected.
- Consumer: neutral dark rectangular card, input slots at left side, type icon, parent layer and channel summary.
- Normal confirmed edge: thin blue curved connection.
- Hovered/selected edge: brighter, thicker, visible input label / tooltip.
- **Confirmed broken** edge: orange/red dashed with error icon **only if confirmed**, not for hypothetical missing data.
- Unsupported/unknown provenance: muted dotted connection or special `?` marker and explanation; never label it broken without evidence.
- Highlight all edges for selected anchor; dim unrelated nodes.
- Empty/orphaned anchor: display alone with `No confirmed consumers` or `No consumers (complete scan)` appropriately.

### Interactions
- Single click node: select in Manager, update inspector, do not unexpectedly change Painter layer selection.
- Double-click source/consumer: locate/select corresponding node in Painter (if supported) and keep Manager selection.
- Hover edge: tooltip `Source -> Input`, input type, channel/mapping and scan confidence.
- Single click edge: inspector switches to Reference Details.
- Right-click source node: Navigate, Focus, Find Uses, Rename, Delete with confirmation.
- Right-click consumer/edge: Navigate to Consumer, Navigate to Anchor, Replace Source, Disconnect (only if host-supported), Copy Path.
- Drag source port onto consumer input port: optional later-stage **connect/replace gesture**, only if validated; otherwise show not-allowed cursor with explanatory tooltip. Never draw a real persisted connection until successful host write.
- Keyboard: arrows or Tab across nodes, Enter for details, F to focus, Esc to close context/operation, Delete opens confirmation (never immediate deletion).

### Performance thresholds
- Up to 100 anchors/500 edges: interactive graph expected without perceptible navigation lag on typical dev machine.
- Above this: progressive rendering, node clustering, optional disable thumbnails, fewer animated effects, and lazy tooltips; avoid repainting entire scene on every mouse move.
- Run document analysis in safe, incremental tasks on Painter's appropriate thread; **do not access Painter host objects from unsafe background threads**. Build/layout pure-data graph outside host APIs if host thread safety is unclear.

---

## 7. INSPECTOR REQUIREMENTS

### Anchor selected
Show:
- Name with Rename pencil; uid in advanced diagnostic tooltip, not prominent.
- Source type: content stack, mask stack or effect chain.
- Texture set, stack/UV tile context where relevant.
- Breadcrumb: `TextureSet / Group / Layer / Content|Mask / Anchor`.
- Placeholder/output preview only when genuinely available.
- `Go to Source` and `Copy Path`.
- `Used By (N known)` list: consumer display name, full breadcrumb, input slot, mapped channels if any, Go and Replace actions.
- `Rename` and `Delete Anchor…` buttons. Destructive action separated visually from normal actions.
- Warning section: name collisions, possible ordering issues, unknown/unscanned consumers, unreadable source metadata.

### Consumer/reference selected
Show:
- Consumer layer/effect name and location.
- Target input slot, mono/split/material source mode, target channel.
- Current anchor name + source location.
- Reference source channel / mapping when supported.
- `Go to Consumer`, `Go to Anchor`, `Replace…`, `Disconnect…` (if supported), `Copy Reference Summary`.
- Validity/capability details.

### Safeguards
- Do not show an interactive Replace button until available candidate sources can be validated or host operation can be safely tested.
- If the source is unavailable, show disabled control with reason instead of dead UI.
- When switching selection while a modal replace dialog is open, that dialog retains a stable immutable target ID and checks its continued validity at confirm time.

---

## 8. CRUD AND REF MANAGEMENT WORKFLOWS

### 8.1 Create anchor
Entry: top toolbar `+ Create Anchor`, plus contextual action on a selected layer/effect.

Dialog/menu behavior:
1. Detect current Painter selection and eligible insertion sites (content, mask, relative to selected effect).
2. Offer only validated insertion locations, e.g. `Selected Layer > Content` or `Selected Layer > Mask`.
3. Suggest name based on layer, editable before commit; do not force a prefix.
4. Show intended path and note stack-order constraints.
5. On confirm: revalidate selection/insertion; perform documented `insert_anchor_point_effect` call; refresh index; select newly created anchor in Manager; report result.
6. On failure: display actual error, preserve previous selection, do not show ghost anchor.

### 8.2 Rename
- Inline F2 or inspector edit.
- Before commit validate non-empty trimmed label, optional warn on name collision within texture set.
- Use documented node rename API after verifying `set_name` in installed version.
- On success reindex display. Name collisions should be warned, not necessarily forbidden if Painter allows them.

### 8.3 Replace one reference
1. Initiate from consumer input edge/inspector.
2. Open modal showing: target layer/effect, exact input/channel, old source, editable new source picker, `Preview changes`.
3. New source picker lists **eligible** anchors in same valid texture-set context; invalid sources disabled with reason (e.g. ordering/cross-set/channel mismatch).
4. Preserve existing mapping/levels/other parameters whenever possible. If change requires resetting settings, disclose this before confirm.
5. Confirm action revalidates anchor and target identities and current host state; only mutate specified source slot.
6. Refresh graph and inspector; clearly identify failed action if host API doesn't support that consumer type.

### 8.4 Replace all uses
1. Entry: source menu `Replace All Uses…`.
2. Choose alternate source.
3. Preview table **per input slot**: consumer path, input channel, old source, proposed new source, eligibility, unsupported status, risk.
4. Default select only safe, supported references; no silent auto-exclusion without explanation.
5. Show `N eligible / M skipped / K unknown` and confirmation button.
6. In single undo transaction when supported, apply changes. Handle partial failure transparently; do not claim atomicity without real rollback.
7. Emit summary: completed, skipped, failed, reasons. Reindex afterward.

### 8.5 Disconnect reference
- Only enable if corresponding source API allows a semantically valid empty/default/unbound state.
- Explain any fallback material/constant source that will replace the current anchor.
- Preview before mutation.
- Never guess that passing `None` disconnects unless docs/runtime confirm.

### 8.6 Delete anchor
- Display number of known uses and discovery-completeness state.
- Default block deletion if usage unknown/incomplete until a full scan or explicit elevated confirmation.
- If used: warn with exact affected references and offer Cancel or `Replace references first` rather than automatic deletion.
- For unused confirmed anchors: confirm deletion, execute supported host deletion API, refresh. Provide undo guidance where supported.
- Never bulk-delete based purely on no edges found by an incomplete index.

---

## 9. VALIDATION, ISSUES, AND ANALYSIS

### Issue taxonomy
`CONFIRMED_BROKEN_REFERENCE`: only if host explicitly reports a dangling source/invalid reference or the manager can prove it from authoritative data.

`INVALID_TARGET_ORDER`: definite ordering violation only where stack hierarchy and evaluation order are correctly known. Otherwise use `POTENTIAL_ORDERING_RISK`.

`UNSUPPORTED_CONNECTION`: source/input found but Inspector cannot edit/read full details using available API. This is *not* broken.

`INCOMPLETE_SCAN`: whole source category or stack segment could not be enumerated; usage counts remain lower bounds.

`DUPLICATE_ANCHOR_NAME`: two or more different anchors share a visible name in one relevant scope; warning only.

`UNUSED_ANCHOR`: only if full discoverable scan is complete and confirmed use count is zero; do not claim full-project unused if unsupported reference categories remain.

`SOURCE_NOT_FOUND` / `STALE_NODE`: an expected identifier no longer resolves after external edits; force reindex before concluding breakage.

### Validation output
- Item severity (info/warning/error), confidence, evidence, source path, consumer path, and suggested action.
- Filter Issues and `Copy diagnostic` which includes host version, feature version, scan coverage, and sanitized paths without unrelated user data.
- Optional manual `Re-scan` button on each issue.
- On renaming or reconnecting, remove stale warning once fresh scan proves resolution.

---

## 10. DATA MODEL / DOMAIN CONTRACTS

Use dataclasses or typed domain objects (avoid exposing direct host objects to UI components). Example conceptual schema, not a rigid serialized format:

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, Dict, List

class Coverage(Enum):
    COMPLETE = 'complete'
    PARTIAL = 'partial'
    UNKNOWN = 'unknown'

class Status(Enum):
    VALID = 'valid'
    WARNING = 'warning'
    BROKEN = 'broken'
    UNKNOWN = 'unknown'

@dataclass(frozen=True)
class NodeKey:
    project_session: str     # ephemeral session token, not persisted as UID guarantee
    texture_set_key: str
    stack_key: str
    host_uid: int

@dataclass
class AnchorRecord:
    key: NodeKey
    name: str
    source_path: Tuple[str, ...]
    stack_domain: str       # content | mask | effect | unknown
    parent_key: Optional[NodeKey]
    use_count_known: int = 0
    usage_coverage: Coverage = Coverage.UNKNOWN
    issues: List[str] = field(default_factory=list)
    preview_token: Optional[str] = None

@dataclass(frozen=True)
class InputSlotKey:
    consumer: NodeKey
    source_mode: str        # mono | split | material | generator_param | unknown
    slot_id: str           # stable within current session as practical
    channel: Optional[str] = None

@dataclass
class ReferenceRecord:
    slot: InputSlotKey
    anchor_key: Optional[NodeKey]
    source_channel: Optional[str]
    channel_mapping: Dict[str, str]
    status: Status
    status_reason: str
    readable: bool
    writable: bool
    discovery_method: str

@dataclass
class GraphIndex:
    anchors: Dict[NodeKey, AnchorRecord]
    references: Dict[InputSlotKey, ReferenceRecord]
    coverage: Coverage
    unsupported_source_kinds: List[str]
    revision: int
```

Design notes:
- `InputSlotKey` uniquely identifies an actual binding slot, not just consumer name.
- Same-named anchors are distinct by host identity.
- Beware UID reuse after project changes: always scope IDs to current project/texture-set session and revalidate before writes.
- Full text paths are for display and diagnostics, not authoritative identity.
- Reference status has uncertainty, not just bool broken/healthy.
- A graph may include an unresolved consumer input with no resolvable anchor if there is evidence of a dangling connection.

### Graph rules
- One anchor -> many input slots (one-to-many).
- One input slot -> at most one current anchor if Painter's API indicates that shape; adapt if composite values permit multiple.
- Distinguish a *consumer object* from *input slot* because channels may have different sources.
- Build reverse lookup for uses: `anchor_key -> list[InputSlotKey]`.
- Build source path index and name search index separately.
- Index is discardable/derived; Painter always authoritative.

---

## 11. RECOMMENDED MODULE ARCHITECTURE

Follow existing repo layout if it already provides equivalents. Suggested conceptual decomposition:

```text
MBToolkit_3DPainter/
  ... existing plugin bootstrap/settings/menu ...
  features/
    anchor_manager/
      __init__.py
      feature.py                  # enable/disable, menu registration, cleanup
      models.py                   # pure typed records
      capabilities.py             # host capability registry/version probes
      painter_adapter.py          # verified Painter calls only
      discovery.py                # layer/anchor/reference walker
      index.py                    # reverse indices, search, coverage
      validation.py               # issue diagnostics
      operations.py               # create/rename/replace/delete, preview/validation
      controller.py               # reactive UI/application state
      ui/
        manager_panel.py          # main dock/container, splitters, toolbar
        anchor_list.py           # search/filter/sort list
        graph_view.py            # graphics scene/canvas and node/edge drawing
        inspector.py             # source and input details
        dialogs.py               # create, replace, impact, confirmations
        styles.py                # consistent Painter-like dark palette
      tests/
        fixtures.py
        test_discovery.py
        test_index.py
        test_validation.py
        test_operations.py
        test_ui_states.py
  ...
```

### Responsibility constraints
- UI never calls `substance_painter` directly. It calls Controller/Services.
- Adapter owns all host API access, capability checks, project readiness, object resolution, and safe-thread execution.
- Discovery creates pure records, including completeness details.
- Validation takes pure graph data plus optional explicit host diagnostic facts.
- Operations use preview -> preflight -> commit -> reread sequence; no optimistic UI commits.
- Event subscriptions registered once, strong callback references maintained, disconnected on plugin close/unload. Dispose widgets and timers.
- Use the MBToolkit shared settings/event/menu infrastructure if it exists.

### Host indexing sketch (pseudocode, not copy-paste API promise)
```
on_project_ready_or_manual_refresh:
    active_texture_stack = host.current_stack()
    root_layers = host.root_layers(active_texture_stack)
    recursively_walk:
        nested group sub_layers
        layer content_effects and mask_effects
        collect every AnchorPointEffectNode
        inspect every supported FillLayer/FillEffect source slot
        inspect other supported consumers only where adapter explicitly knows how
        record unsupported source categories as coverage gaps
    resolve SourceReference.anchor identities
    build reverse usage index and graph layout input
    validate only evidence-supported conditions
    display results
```

### Discovery completeness handling
Maintain coverage at both **global** and **per-input-kind** levels:
- Multi-channel fill material source
- Split source per active channel
- Mono mask-stack fill source
- Generator/filter embedded source or parameters (possibly partial/unsupported)
- Other supported source-reference-bearing features if discovered

A complete scan of *known fill reference slots* does not prove there are no *generator-specific* references. UI should describe exact coverage. For user-facing total counts, choose precise labels over apparently definitive numbers.

### Safe updates / synchronization
- Subscribe to ProjectEditionEntered, ProjectEditionLeft/close, LayerStacksModelDataChanged, and other relevant available events.
- Debounce layer-stack change events (~250–500ms) and coalesce bursts.
- Check if project is in editable/not-busy state before writes. If host busy, queue safely or disable edit controls.
- Refresh only when active texture-set/stack or layer state changes; selection change ideally updates inspector without full deep index.
- Make refresh cancellable or abandon obsolete results via revision token.
- If UI window is closed, stop expensive scans; optionally keep a small cached index while project remains open.
- Avoid polling constantly. If current texture-set change notifications are unavailable, use a light timer while panel visible and compare active stack key; never heavy-scan every tick.

### Undo and transactions
Use documented `layerstack.ScopedModification` for supported batches when helpful; verify which methods may be called inside that scope and do not call `set_selected_nodes` inside it because the API documents this as invalid. Separate mutation transaction from UI navigation/selection.

---

## 12. UI COMPONENT DESIGN TOKENS

This is a **desktop tool**, not a website. Prefer native Qt layouts, painter-compatible toolbar/buttons/list views, QSplitter and QGraphicsView or another performant Qt graph canvas.

- Primary background: near-black charcoal `#161B21`.
- Secondary panels: `#20262D`; raised cards `#252D36`.
- Borders/dividers: subdued slate `#3A4652`.
- Primary text: cool off-white `#E9EEF3`; secondary `#9EAFBD`.
- Accent blue/cyan: `#2FAAE8`, selection outline `#249ADB`.
- Warning amber: `#F4A340`; error coral-red: `#E5675F`.
- Radius 4–8px; row/list height ~44–60px depending on preview setting.
- Compact property labels small; most frequent actions remain obvious.
- Icons must have accessible tooltips and predictable click targets.
- Respect host HiDPI scaling, font differences, and theme behavior; palette values are guidance, not requirement to fight host styling.
- Do not use animated glowing lines, visual clutter, oversize thumbnails, or distracting graphs by default.

### Key components
- TextureSetSelector
- AnchorSearchBar
- AnchorFilterChips
- AnchorListModel and item delegate
- AnchorGraphCanvas
- SourceAnchorNodeItem / ConsumerNodeItem / InputPortItem / ReferenceEdgeItem
- GraphToolbar
- AnchorInspector / ConsumerInspector
- AnchorCreateDialog / ReplaceReferenceDialog / ImpactPreviewDialog / ConfirmDeleteDialog
- StatusBar and ScanCoveragePopover
- EmptyState / LoadingState / ErrorState

### Accessibility/interaction requirements
- Tooltips for ambiguous statuses and unsupported buttons.
- Keyboard-focused list and modal operations; press Esc to dismiss.
- Selection color also paired with shape/outline so it is not color-only.
- Persist UI mode / splitters but not invalid identities.
- A graph-only interface is not enough: all reference actions accessible in searchable textual lists.

---

## 13. TEST PLAN

### Pure Python tests (no Painter)
1. Recursive hierarchy traversal with groups/content/mask/effects.
2. Duplicate names remain independent records.
3. One anchor -> multiple distinct input slots is counted correctly.
4. One consumer -> several channels/sources yields distinct edges.
5. Partial scan never yields definitive `Unused`.
6. No false confirmed broken state when target/source merely unobservable.
7. Rename updates search index after refresh.
8. Switching texture sets invalidates old graph and selection cleanly.
9. Replace preflight rejects cross-set, missing source, missing target, invalid channel/order where detectable.
10. Mutation failure produces no false-success UI state.
11. Batch preview reports supported, skipped and unknown correctly.
12. Stale UID is detected and triggers reindex/revalidation.
13. Graph layout is deterministic from same fixture and maintains readable separation for hundreds of nodes.
14. Debouncing coalesces duplicate refresh events.
15. UI handles empty/loading/partial/error states.

### Manual Painter smoke test matrix
- Host oldest supported build, one middle build if available, and latest installed build.
- Empty project/no project; one texture set; multiple texture sets.
- Anchor in fill layer content; anchor in mask stack; anchor adjacent to effect.
- Single-channel mask reference; material/multi-channel fill reference; split per-channel fill references.
- Generator with potential anchor-related inputs: verify whether and how exposed.
- Anchor renamed in native Painter UI while Manager is open.
- Consumer changed in native Painter UI while Manager is open.
- Anchor inserted/deleted in native Painter UI; observe refresh.
- Rapid project switching/close with Manager open.
- Large layer stack and nested groups.
- Duplicate anchor names.
- Invalid selection/action and undo/redo.
- Qt reload/re-enable/disable plugin without stale event handlers or duplicate menu entries.

### Acceptance criteria by milestone
**M1 (read-only usable):** correct anchor library, search, native navigation, source paths, discoverable use counts with coverage labels, focus graph, inspector, no crashes on empty/large projects.

**M2 (editorial):** create + rename, per-reference replacement for documented fill-source contexts, safe modal previews, transactions/undo where verified, accurate status/reporting.

**M3 (advanced):** replace all, cleanup, richer consumer-source adapters, issues report, compact/full graph modes, opt-in graph drag-connect if reliable.

**M4 (polish):** optional previews, broader compatibility shims, large-graph clustering, keyboard UX, docs and packaging.

No milestone should be marked done without the listed smoke checks, or without explicitly documenting tests impossible to perform.

---

## 14. DEVELOPMENT AND DELIVERY SEQUENCE FOR VS CODE AGENT

1. **Inspect project:** identify version, feature registry, `__init__.py`, existing menu/prefs, Qt setup, test conventions. Summarize before modifying.
2. **Inspect documented API:** verify call names against installed Painter (when available), and create a capability matrix for each operation: find anchors; read material/split/mono source; find generators' references; create; rename; select; replace; delete; thumbnail; event subscribe.
3. **Build typed domain + host adapter:** separate host calls from UI. Write fixture adapter first.
4. **Write traversal/index tests:** ensure accurate recursion and coverage semantics.
5. **Build functional list + inspector:** usable even with graph disabled; refresh, search, filters, source navigation.
6. **Build graph:** deterministic producer-left/consumer-right layout, readable edges and interaction, Focus mode first, Overview second.
7. **Integrate Painter:** wire active texture set, ProjectEditionEntered/Left, LayerStacksModelDataChanged, safe refresh and navigation.
8. **Create/rename/relink:** only verified supported operations with impact/preflight dialogs.
9. **Issues + cleanup:** strict confirmed-vs-unknown categories, unused only if scan is complete.
10. **Version compatibility + UX polish:** capability checks, fallback control states, performance testing and teardown.
11. **Final deliverables:** code changes, tests, setup README, compatibility table, known limitations, exact instructions to enable/open the feature, manual test checklist.

### Agent coding guidelines
- Do not ask the user for an opinion on routine design decisions; follow this specification.
- Never remove existing MBToolkit features to make this module run.
- Avoid giant single-file implementation; keep modules reasonably cohesive.
- Type annotate service boundaries; log useful structured errors.
- External runtime dependencies should be minimal, ideally Painter Python + available Qt binding + Python standard library.
- Prefer neutral service interfaces to allow mock testing and future reuse by other MBToolkit modules (e.g., Layer Manager).
- Test all pure business logic locally. If Painter unavailable in the VS Code runtime, do not claim in-host verification; document precise remaining manual checks.
- Clearly distinguish implemented/working features from gated/skipped features in delivery summary.

---

## 15. PRODUCT DECISIONS / EDGE CASES

- **Anchor output thumbnail not available:** show source-type icon plus name, optional lazy thumbnail later; do not rely on screenshots or invasive export in default browsing flow.
- **Zero references found with incomplete coverage:** show `0 known` + `Scan partial`; exclude from `Unused` cleanup.
- **Multiple same-named anchors:** show different breadcrumbs and identities, allow selecting either.
- **Invalid/cross-set source requested:** disable candidate and explain Painter limitation.
- **Ordering validity ambiguous:** warn about *potential* order problem rather than saying broken.
- **Owner layer deleted during open dialog:** disable confirmation after revalidation and offer refresh.
- **Active texture set changes while graph open:** clear outdated selection; load new graph, don't repoint previous UIDs automatically.
- **Source parameters unavailable to Python:** show `Not available in this Painter version` and a navigation affordance to Painter's native properties rather than pretending to edit.
- **Undo/redo:** schedule index refresh; never keep optimistic graph state independent of Painter.
- **Very large graphs:** auto-switch to Focus or grouped overview, with informative banner `Overview simplified for performance`.
- **No active layer selection:** Create button opens disabled insertion-state explanation rather than inserting in an arbitrary stack location.
- **Permissions or read-only state:** viewing remains available, writes disabled.
- **Close/reload plugin:** no leaked widgets, duplicate menus, dangling callbacks, or timers.

---

## 16. FUTURE ENHANCEMENTS (DO NOT BLOCK CORE RELEASE)

- Named anchor collections/favorites and filtered bookmarks.
- Usage history/change comparison between saved project revisions (requires reliable identity strategy).
- Anchor naming templates and team style validation.
- Material graph readability aids: node grouping, labels, notes, snap/grid.
- Export anchor inventory/diagnostic as JSON and human-readable Markdown.
- Impact preview that optionally highlights affected layers in Painter viewport (only with safe host capability).
- Suggested reconnect candidates for confirmed broken references, **never auto-applied**.
- Consolidate identical references or identify duplicate anchors where semantics can be safely proven.
- Search/command-palette integration and shared MBToolkit shortcuts.
- Tooltips with source/output map previews when a real API-backed preview exists.

---

## 17. QUICK EXECUTION PROMPT

> Build the Anchor Manager module of the existing MBToolkit_3DPainter plugin according to this specification. First inspect the repository and real Painter Python API capabilities. Implement the read-only anchor discovery/index/list, dependency visualization, native navigation and inspector as a complete useful initial slice, then progressively add supported create/rename/reference-edit actions with safe previews, robust tests, and graceful fallbacks for unsupported capabilities. Preserve the current MBToolkit architecture and all other features. Do not fabricate host API methods or imply unsupported behavior works. Provide a compatibility matrix and precise in-Painter smoke test steps.

---

## 18. FINAL FEATURE CHECKLIST

### Core
- [ ] MBToolkit feature toggle / menu entry / preferences / safe teardown
- [ ] Dockable responsive manager + expanded graph option
- [ ] Texture-set-aware anchor enumeration and hierarchy paths
- [ ] Search, usage and issue filters, sort, selected-layer scope
- [ ] Native navigation to source and consumer
- [ ] Graph Focus mode, Overview, connection details and legible layout
- [ ] Inspector with source/consumer/slot/channel context
- [ ] Accurate scan coverage and reference counts
- [ ] No false unused/broken claims

### Editing
- [ ] Contextual create anchor
- [ ] Rename anchor
- [ ] Replace one supported input source
- [ ] Preview and validate replace-all
- [ ] Optional supported disconnect
- [ ] Safe delete and unused cleanup
- [ ] Undo-safe grouped edits where API supports them

### Reliability
- [ ] Debounced live refresh and manual refresh
- [ ] Project close, texture-set switch, undo/redo, stale-object handling
- [ ] Feature/capability version adapters, disabled unsupported actions
- [ ] Fake host tests and real Painter smoke checklist
- [ ] Large-project responsiveness and visual clarity
- [ ] Good exception messages, safe fallback, documented limitations

**END OF SPECIFICATION**
