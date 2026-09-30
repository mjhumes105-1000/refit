# REFIT

**Rapid Electronics Form-fit-function Integration Tool** is an AI-assisted pipeline for rapidly reverse engineering and modernizing legacy military circuit card assemblies (CCAs).

> Independent personal project, built only from open-source tools and public-release information. It is not affiliated with, endorsed by, or funded by the U.S. Navy, the Department of Defense, or any government agency. It uses no controlled, CUI, or export-controlled data.

## The problem

Older cards in fielded systems fail, and their parts are no longer made. Often the original manufacturer no longer exists. What remains is usually a scanned technical manual: a schematic, a parts list full of obsolete part numbers, and no CAD files.

Building a trustworthy replacement can take months. In the meantime, units often cannibalize ("CANN") cards from other ships or systems, which turns one casualty into two degraded platforms.

Fabrication is not the bottleneck; board shops can build replacements at volume. The bottleneck is the engineering, and the evidence needed to approve the change.

## What REFIT does

It turns a legacy card's documentation (plus optional board photos) into a modernized, verified replacement design:

```
scanned technical manual ──► verified netlist ──► functional blocks ──► obsolescence report
                                                                             │
   KiCad schematic + report + PDF library ◄── simulation equivalence ◄── justified substitutions
```

Three principles run through every stage:

- **AI proposes, rules check, humans approve.** Every fact (a part value, a connection, a substitution) is a claim carrying its evidence (page and region of the manual, photo, or datasheet), what produced it, and a confidence level.
  - Confidence comes from cross-checks, not from the AI rating itself.
  - Anything low-confidence, or anything that fails a rule check, goes to a review queue instead of being silently accepted.
- **Honest metrics.** The target is for the AI to do 50–70% of the analysis. Automation is measured against a hand-built reference netlist, and the false-accept rate is reported right beside it.
- **Configuration first.** The pipeline won't export a design until a human confirms the card revision, the manual edition, and the host system version. A perfect redesign of the wrong revision is worse than none.

## Status

| Milestone | State |
|---|---|
| 1. Demo card selection + hand-built reference netlist | in progress |
| 2. Foundation: Card Record, review queue, metrics, model adapter, intake, configuration gate, CLI | **built** |
| 3. Parts list + schematic extraction + synthetic benchmark | planned |
| 4. Functional blocks, obsolescence, substitution | planned |
| 5. Simulation equivalence (ngspice, Icarus Verilog) | planned |
| 6. Export: KiCad schematic, modernization report, updated PDF reference library | planned |
| 7. Photo evidence (component ID, marking OCR, revision cross-check) | planned |

Design: [`docs/superpowers/specs/2026-09-30-refit-design.md`](docs/superpowers/specs/2026-09-30-refit-design.md)

## Distribution A only

REFIT processes **only** technical manuals marked **Distribution Statement A** (approved for public release; distribution is unlimited).

- Intake reads the statement printed on the manual's own cover pages; where the manual was found doesn't count.
- It hard-stops on a missing statement, or on any non-A statement anywhere on those pages.
- If a cover is scanned with no text layer, the AI only transcribes it. A fixed rule, not the model, decides whether it's Distribution A.

Third-party board photos and manufacturer datasheets are referenced by link and hash, and are never committed to this repository.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest -q
```

Intake a manual (live AI calls need `ANTHROPIC_API_KEY` or an `ant auth login` profile):

```bash
uv run refit intake servo-card --manual https://example.org/tm-11-xxxx.pdf --host-system "AN/XXX-1" --card-rev C
```

Work the review queue, then confirm the configuration:

```bash
uv run refit review servo-card
uv run refit accept servo-card rv:config:tm_number --by "your name"
uv run refit resolve servo-card rv:config:tm_edition --value "1 June 1985" --by "your name"
uv run refit confirm-config servo-card --by "your name"
```

Score the pipeline against a hand-built reference:

```bash
uv run refit metrics servo-card --reference reference.json
```

| Command | Purpose |
|---|---|
| `intake` | Stage 0: fetch the manual, apply the Distribution A gate, build the configuration baseline |
| `review` | List open review items |
| `resolve` / `accept` | Settle a review item with a corrected value, or accept what was proposed |
| `override` | Correct any fact, including ones that were accepted automatically |
| `confirm-config` | Human confirmation of the configuration baseline |
| `metrics` | Automation and false-accept rates against a reference |
| `schema` | Export the Card Record JSON Schema |

Add `--replay` to `intake` to run only from cached model replies, with no live calls.

## How it's built

- **Card Record:** Pydantic models saved as JSON. Each stage writes its own snapshot (`cards/<id>/card.sNN.json`) and never edits earlier ones.
- **Human decisions:** kept in `cards/<id>/overrides.json` and re-applied after every run, so re-running the AI never erases a correction.
- **Model adapter:** the only way stages reach an AI model. It validates replies against a schema, retries once, and caches valid replies for deterministic replay. The model can be swapped per stage, including for local or air-gapped models.
- **Default model:** Claude (Opus 5.5), with server-side refusal fallback.
- **Verification (planned):** ngspice for analog blocks, and Icarus Verilog plus timing and electrical checks for digital blocks. The manual's own test-point voltage tables serve as ground truth.

## Credits

Built with [Claude Code](https://claude.com/claude-code). Uses [Pydantic](https://docs.pydantic.dev/), [PyMuPDF](https://pymupdf.readthedocs.io/), [httpx](https://www.python-httpx.org/), and the [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python).
