# REFIT — Design Spec (Sub-project 1: Scan-to-Modern-Package)

**REFIT** — *Rapid Electronics Form-fit-function Integration Tool*
Date: 2026-09-30 · Status: draft for review

---

## 1. Purpose and context

### Problem
Legacy circuit card assemblies (CCAs) in fielded Navy and military systems fail, and
their parts are obsolete (DMSMS). The original manufacturer is often gone and CAD data
never existed; what remains is a degraded technical data package — scanned schematics
and parts lists in a technical manual (TM). Engineering a trustworthy form-fit-function
(FFF) replacement takes months. Meanwhile, deployed units cover the gap by
cannibalizing (CANN) cards from other ships, turning one casualty into two degraded
platforms and extending CASREPs.

Fabrication is not the bottleneck — PCB fab/assembly shops (including ITAR-registered
ones) can produce replacements at volume. The bottleneck is the upstream engineering
and the evidence needed to approve the change.

### Goal
A public showcase that could seed a startup. REFIT turns a legacy card's documentation
(plus optional board photos) into a modernized, simulation-verified replacement design
and a documentation package a depot or program office would take seriously.

**Long-term vision (not this sub-project):** larger comms and combat-system CCAs;
measurably reducing CANNs and CASREP time for deployed ships.

### Success criteria for sub-project 1
One real, Distribution A card goes from scanned TM pages to:
1. A verified netlist
2. A functional-block breakdown
3. An obsolescence report
4. Justified, ranked substitutions (human-approved)
5. A per-block simulation equivalence report
6. A modernized KiCad schematic
7. An updated PDF reference library

— all reproducible from the repo plus a local cache, with a measured automation rate
in the **50–70%** range and a prominently reported false-accept rate.

### Principles
- **AI proposes, rules check, humans approve.** The AI never has the final word on a
  netlist connection, a substitution, or a configuration.
- **Every fact has evidence.** Page + region, photo, datasheet, or API response.
- **Honest metrics.** Automation is measured against a hand-built reference; false
  accepts are reported, not hidden.
- **Model-swappable.** No stage calls an AI provider directly, so the pipeline can later
  run on local/air-gapped or accredited-cloud models for CUI/ITAR boards.
- **Publish only what we may publish.** Distribution A manuals only; third-party photos
  and datasheets are referenced by link and hash, never committed.

---

## 2. Architecture

A pipeline of ten independent stages. The only thing stages share is the **Card
Record**. Each stage reads the previous snapshot and writes a new one, so any stage can
be re-run alone.

| # | Stage | Responsibility | Mechanism |
|---|---|---|---|
| 0 | Intake | Fetch manual + photo links; record sources and hashes; **Distribution A gate**; capture configuration baseline | Deterministic + cover-page OCR |
| 1 | Page triage | Classify pages: schematic, parts list, component location diagram, theory of operation, test-point tables, notes | Vision model |
| 2 | Parts list | Extract ref des, mil/commercial part numbers, NSN, CAGE, value, tolerance, description | Vision/OCR → rule checks |
| 3 | Schematic | Symbols, pins, nets; cross-sheet merge; implicit power pins | Vision model + classical CV → rule checks |
| 4 | Photo evidence *(optional)* | Component locate/ID, marking read, ref des mapping, mismatch flags | Vision model + image registration |
| 5 | Blocks | Segment into functional blocks; infer function; link theory-of-operation text | Language model |
| 6 | Obsolescence | Mil→commercial part mapping; lifecycle status | Distributor APIs (deterministic) |
| 7 | Substitution | Derive operating envelope; candidates; filters; tiered ranking; rationale; sim models | Language model + parametric filters |
| 8 | Equivalence | Original vs modern per block; corners + Monte Carlo; TM test-point checks | ngspice, Icarus Verilog (deterministic) |
| 9 | Export | KiCad schematic, modernization-package report, updated PDF reference library | Deterministic |

**Cross-cutting components**
- **Rule checks** — run after every stage; failures become review items.
- **Review queue** — collects low-confidence facts and check failures. It is the source
  of the automation metric and, later, the backend of the review app (sub-project 3).
- **Model adapter** — single interface for vision and text calls, selectable per stage.
  Responses are cached by (prompt version, model, input hash) for replay.
- **Configuration gate** — see §3.3. Export is blocked until configuration is
  human-confirmed.

### Repository layout (target)
```
REFIT/
  refit/
    record/        # Card Record schema (Pydantic), snapshot I/O, overrides
    stages/        # s00_intake.py … s09_export.py, one module per stage
    checks/        # rule checks, one module per check family
    review/        # review queue, metrics
    models/        # model adapter + providers + response cache
    sim/           # netlist generation, ngspice/iverilog runners, measurement templates
    libs/          # 74-series Verilog models, behavioral SPICE model generator
    export/        # KiCad writer, report templates, PDF library builder
  bench/           # synthetic schematic benchmark (render + degrade + score)
  cards/<card-id>/ # per-card workspace: snapshots, overrides.json, reference netlist
  cache/           # gitignored: manuals, photos, datasheets, API + model responses
  tests/
  docs/
```

---

## 3. Card Record

### 3.1 Design rules
1. **Pydantic v2 models, JSON on disk**, with an exported JSON Schema and a schema
   version field.
2. **Snapshot per stage** — `cards/<id>/card.s03.json` etc. Stages never edit earlier
   snapshots, so runs can be diffed.
3. **Separate overrides file** — `cards/<id>/overrides.json` holds every human decision.
   It is re-applied after each stage run, so re-running AI never erases a correction. It
   is also labeled training data for a future custom schematic reader.
4. **Every fact is a Claim:** `value`, `confidence`, `evidence[]`, `produced_by` (stage,
   model + prompt version, rule, or human), `status` ∈ {proposed, accepted, flagged,
   overridden}.
5. **Confidence is derived from cross-checks, not model self-report:** agreement between
   independent reads, parts list ↔ schematic agreement, pin count ↔ package, photo ↔
   parts list. A fact that fails a cross-check is flagged regardless of model certainty.
   A fact is auto-accepted only if it passes every applicable check **and** its
   confidence meets the category threshold (default 0.9, configurable per category,
   calibrated on the synthetic benchmark). Connections additionally require agreement
   between the CV trace and an independent model read.

### 3.2 Entities

| Entity | Key contents |
|---|---|
| **Card** | Assembly part number, revision, NSN, title; source manual (TM number, edition, date, distribution statement) |
| **ConfigurationBaseline** | Card PN + revision letter; TM edition + applied change numbers; TM effectivity (serials/models covered); applicable field changes / modification orders; host system end-item model + modification level; `confirmed_by` / `confirmed_at` |
| **Source** | Manual PDF, photo URL, datasheet URL, API response; SHA-256; license/distribution; `publishable: bool`; local cache path |
| **Evidence** | Source ID, page, bounding box, excerpt, method |
| **Part** | Ref des; mil/commercial/NSN part numbers; CAGE; value; tolerance; rating; package; pins (number, name, role); domain (analog/digital/power/passive/programmable); photo location |
| **Net** | Stable ID derived from sorted member pins; members `(refdes, pin)`; label (e.g. `+15V`, `TP3`); `is_power` |
| **Block** | Name; inferred function; member parts; input/output nets; domain; linked theory-of-operation excerpt |
| **TestPointSpec** | Net; operating condition; expected voltage/waveform + tolerance; source evidence |
| **LifecycleStatus** | Per part: active / NRND / EOL / obsolete / unknown; source; date checked |
| **Substitution** | Original ref des + part → ranked candidates, each with parameter comparison table, pin-compatible flag, tier (1/2/3), required circuit changes, rationale with datasheet evidence, sim-model quality (vendor / behavioral); `selected` requires human approval |
| **EquivalenceResult** | Per block: sim type, stimulus, conditions, measured quantities, thresholds, verdict (pass / pass-with-deviations / fail / unverified), plot paths, model-quality tag |
| **ReviewItem** | Target fact; reason (low confidence or named failed check); proposed value; resolution (value, who, when) |

### 3.3 Configuration gate
- Intake populates the ConfigurationBaseline from the TM cover, change pages, and
  effectivity statements; photo evidence adds observed PN/revision.
- Any disagreement between photo revision, TM effectivity, and stated host-system
  version becomes a blocking review item.
- **Stage 9 refuses to export** unless `ConfigurationBaseline.confirmed_by` is set by a
  human. A redesign of the wrong revision is worse than none.

### 3.4 Automation metric
Computed per category (parts, connections, blocks, substitutions) against the
hand-built reference (§7.2):
- **Automation rate** = facts auto-accepted **and** correct ÷ total facts
- **False-accept rate** = facts auto-accepted **but** wrong ÷ auto-accepted facts

Targets: automation 50–70%; connection false-accept rate < 2% (initial target, tuned
once real numbers exist). The report shows both side by side.

---

## 4. Stage details

### Stage 0 — Intake
- Inputs: TM PDF (URL or local path), optional photo URLs, host-system description.
- OCR the cover/title pages; parse the distribution statement. **Hard stop on anything
  other than Distribution A**, regardless of where the file was found.
- Hash and cache every source. Third-party photos and datasheets: `publishable=false`.

### Stage 1 — Page triage
- Render pages at high DPI (PyMuPDF). Vision model classifies each page; fold-out pages
  are detected by aspect ratio and handled as large schematics.

### Stage 2 — Parts list
- Table extraction by vision model, cross-validated with OCR text.
- Checks: ref des unique; ref des format valid; part-number formats (JAN, M-spec, NSN)
  well-formed; quantities consistent.

### Stage 3 — Schematic extraction (highest technical risk)
1. **Pre-process** — deskew, denoise, sharpen; tile fold-outs into overlapping tiles
   with page coordinates.
2. **Symbols and labels** — vision model per tile: symbol type, ref des, value, pin
   positions and labels, with bounding boxes.
3. **Wire tracing (classical CV)** — OpenCV line detection, skeletonization,
   junction-dot detection; build a wire graph; snap wire endpoints to pin positions.
   Crossings without a dot are *not* connections.
4. **Independent second read** — targeted vision-model queries on ambiguous nodes
   ("what connects to U3 pin 6?"). Agreement raises confidence; disagreement → review.
5. **Cross-sheet merge** via off-page connectors and net labels.
6. **Implicit power pins** — extract notes such as "U1–U8: pin 14 +5 V, pin 7 GND" and
   add those connections.

Checks: every parts-list ref des placed (multi-unit aware, e.g. U1A/U1B); pin count vs
package; no single-pin nets except test points and NC; no output-to-output ties; power
pins connected; op-amps have a feedback path.

### Stage 4 — Photo evidence (optional)
- Register the TM component location diagram onto the photo (feature matching +
  homography) to predict each ref des position.
- Crop per component; vision model reads markings; compare with parts list.
- Flag mismatched, missing, or revision-inconsistent parts; feed observed PN/revision
  to the configuration baseline.
- Scope limit: no trace extraction from photos.

### Stage 5 — Blocks
- Language model segments the netlist into functional blocks using topology and
  theory-of-operation text; each block gets defined input/output nets and a domain.
- Checks: every part in exactly one block; block interfaces consistent with nets.

### Stage 6 — Obsolescence
- Map mil part numbers to commercial generics (e.g. `JAN2N2222A` → 2N2222A,
  `M38510/…` → 54-series, `RNC55` resistors, `M39003` capacitors).
- Look up lifecycle status via distributor APIs (Nexar/Octopart, DigiKey, Mouser);
  cache responses with dates.
- Programmable parts (PROM/PAL/EPROM/firmware) → flagged **unresolvable without a
  chip readout**; never guessed.

### Stage 7 — Substitution
1. **Operating envelope** — what the circuit demands: supply rails, signal bandwidth,
   output current, input range, slew rate, and the card's temperature grade (often
   −55 to +125 °C). Language model reads the block and theory text; rules compute what
   they can (e.g. required gain-bandwidth from feedback network and signal frequency).
2. **Candidates** — distributor parametric search filtered by package/pinout family,
   plus model knowledge of standard cross-references.
3. **Hard filters (rules)** — pin compatibility or explicit adaptation; supply range;
   temperature grade; through-hole package; active lifecycle; prefer multi-source.
4. **Tiers** — 1: drop-in FFF; 2: drop-in + value change (e.g. compensation cap);
   3: circuit change. Tier 1 preferred (lowest requalification burden).
5. **Mandatory gotcha checklist**, each addressed with datasheet evidence: TTL vs CMOS
   thresholds (74LS → 74HCT, not 74HC); output drive / fan-out; faster edges →
   ringing/EMI; op-amp common-mode range and phase reversal; capacitive-load stability;
   power-up behavior.
6. **Sim models** — vendor SPICE model where available; otherwise a behavioral model
   generated from datasheet parameters (for the obsolete original too), tagged
   lower-confidence.

### Stage 8 — Equivalence harness
- **Unit of comparison:** each block, original vs modern, identical stimulus and
  conditions. Netlists are generated from the Card Record and saved; random seeds fixed.
- **Conditions:** nominal; supply ±5% and ±10%; card temperature range (e.g. −55, 25,
  +125 °C); Monte Carlo 200–500 runs over parts-list tolerances.
- **Analog measurement templates** by block type:
  - Amplifier/filter: gain and phase vs frequency, bandwidth, DC offset, output swing,
    step response (overshoot, settling)
  - Regulator/power: output vs load and line, ripple, start-up transient
  - Comparator/oscillator: threshold, hysteresis, frequency, duty cycle
- **Pass criterion:** modern results fall inside the original's Monte Carlo envelope and
  within any TM-stated limits.
  - **Pass**
  - **Pass-with-deviations** — modern part is better/different (e.g. faster); routed to
    review, never auto-passed
  - **Fail**
  - **Unverified** — models insufficient to simulate, or the original failed the TM
    test-point check (see below); never counted as a pass
- **Digital, three layers:**
  1. Logic equivalence — structural Verilog from a 74-series behavioral library,
     Icarus Verilog; exhaustive vectors for combinational blocks with ≤16 inputs;
     directed + random vectors, cycle-by-cycle compare for sequential blocks.
  2. Timing — datasheet min/max propagation delays along paths; flags designs that
     depend on slow parts (races, RC delays, one-shots).
  3. Boundary electrical — VOH/VOL vs VIH/VIL and fan-out current budgets at
     analog/digital boundaries; ngspice mixed-mode simulation for boundary blocks.
- **TM ground truth, two-way check:**
  - Original sim vs TM test-point tables → validates **extraction** (netlist + models).
    A mismatch blocks substitution judgments for that block.
  - Modern sim vs original sim → validates **substitution**.
- **Outputs:** EquivalenceResult per block; Bode overlays, Monte Carlo envelopes, timing
  diagrams; failures and deviations → review queue.

### Stage 9 — Export
Blocked until the configuration gate is confirmed. Produces:
1. **Modernized KiCad schematic** (written via a Python KiCad file library).
2. **Modernization-package report** (HTML → PDF): configuration baseline; original vs
   modern schematic side by side; obsolescence table; substitutions with rationale;
   equivalence verdicts and plots; review-queue summary; automation and false-accept
   metrics.
3. **Updated PDF reference library** (one indexed, bookmarked PDF per card):
   - Updated TM-style schematic and parts-list pages with change bars marking
     modifications
   - Datasheets for every original and replacement part
   - Obsolescence status and configuration baseline
   - Cross-links from each ref des to its datasheet and substitution rationale

   The public repo includes the pages REFIT authors; manufacturer datasheets are
   referenced by URL + hash, and the full library is assembled locally.

---

## 5. Review queue
- Every flagged claim, failed check, pass-with-deviations verdict, substitution
  selection, and configuration confirmation becomes a ReviewItem.
- Sub-project 1 interface: CLI (`refit review <card>`) listing items with evidence
  crops, accepting a resolution that is written to `overrides.json`.
- The sub-project 3 web app will be a UI over this same data; no schema change needed.

---

## 6. Error handling
- **Stage failure** — a stage that cannot complete writes no snapshot and exits with a
  clear error; earlier snapshots remain valid.
- **Model errors / malformed output** — adapter validates responses against the
  expected Pydantic shape, retries once, then records a ReviewItem rather than
  inventing a value.
- **Missing sim model** — generate behavioral model; if datasheet parameters are
  insufficient, the block verdict is `unverified`, never `pass`.
- **Distribution gate / configuration gate** — hard stops with an explicit message.
- **External API outage** — use cache if present; otherwise mark lifecycle `unknown`.

---

## 7. Testing and validation

### 7.1 Test suite
1. **Rule checks, test-first** — each check has a deliberately broken netlist fixture
   that must trigger it.
2. **Synthetic schematic benchmark** (`bench/`) — render open-source KiCad projects with
   known netlists to images, degrade them (blur, skew, photocopy noise, fold creases,
   faded lines), run stage 3, and score precision/recall vs degradation level.
3. **Replay mode** — cached model responses make the suite deterministic and free; live
   model evaluations run separately on demand.
4. **Harness positive and negative controls** — known-good substitutions must pass;
   known-bad ones must fail (74HC driven by TTL output; op-amp with insufficient
   bandwidth; too-fast part in a delay-dependent circuit).
5. **End-to-end smoke test** of the demo card in replay mode.

### 7.2 Hand-built reference
- The demo card's netlist is hand-built in KiCad directly from the TM, **before**
  viewing pipeline output.
- Pipeline output is diffed against it; every disagreement is adjudicated (either side
  may be wrong). This reference is the denominator for §3.4 metrics.

---

## 8. Demo card selection (first milestone)
A research pass shortlists 3–5 candidates for the user to choose from. Criteria:
- Distribution A TM with legible schematic, parts list, component location diagram,
  test-point voltage/waveform tables, and theory of operation
- Mixed-signal, through-hole, roughly 30–100 components
- Contains genuinely obsolete active parts
- Obtainable as surplus for later bench testing
- Navy/military relevance preferred

---

## 9. Stack
Python 3.12 (uv) · Pydantic v2 · OpenCV · PyMuPDF · ngspice · Icarus Verilog ·
Python KiCad file library · Jinja2 HTML → PDF · Anthropic SDK behind the model adapter.
Windows-compatible. Public GitHub repo; per-card workspaces and caches stay local until the user
chooses to publish.

---

## 10. Scope

### Out of scope for sub-project 1
- Board layout, Gerbers, manufacturing files (sub-project 2)
- Review web app (sub-project 3)
- Trace extraction from photos or X-ray (physical capture)
- Bench-test procedure generation (later; user has bench-test access)
- Air-gapped / CUI deployment (only the model-adapter seam is built)
- Qualification and approval paperwork
- Contents of programmable parts (flagged, not recovered)

### Build order
1. Demo card selection + hand-built reference netlist
2. Card Record schema, intake, configuration gate
3. Parts list + schematic extraction + synthetic benchmark
4. Blocks, obsolescence, substitution
5. Equivalence harness
6. Export: KiCad, report, PDF reference library
7. Photo evidence

### Future sub-projects
2. Layout / FFF board generation (outline, connectors, mounting preserved)
3. Review web app over the review queue
4. Physical capture (photos/X-ray → netlist) and bench-test procedure generation
5. Larger comms and combat-system CCAs; controlled-data deployment
