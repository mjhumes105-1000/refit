# Demo card verification: USCG Model 066 Searchlight Positioner, card A5

The user selected this card on 2026-09-30. Manual: *Technical Manual for Model 066 Searchlight Positioner*, Contraves Goerz Corp., effective 2 May 1983, USCG-7610-0-GF2-0201, DTIC AD-A139850.

Source: https://archive.org/details/DTIC_ADA139850. The PDF is 6.4 MB and 183 pages, cached locally at `cache/manuals/DTIC_ADA139850.pdf` (git-ignored).

## Distribution: verified (visually)
PDF page 4, the manual's own cover, carries the stamp **"This document has been approved for public release and sale; its distribution is unlimited."** I confirmed it on the rendered page image.

**REFIT intake gate result: fails closed (correct behavior, but intake can't run yet):**
1. **Page 4 is outside the gate's 3 cover pages.** Pages 1–3 are DTIC front matter: a microfiche header and the "microcopy resolution test chart".
2. **The OCR text layer is garbled:** `This document has been avPp!Ov~ ~for public release and sale; its distributionl is unlimited.` The regex can't match it.

Gate change (implemented 2026-09-30):
- Read past DTIC front matter (for example, scan the first 6 pages).
- When the text layer holds no statement, fall back to the model transcribing the page images. That path already sends the statement to human review (`config:distribution_statement`), so the gate stays fail-closed and human-confirmed.

## Card A5: Searchlight Control Card I (P/N 703711-1, manufacturer code 51261)

| Element | PDF page | Manual reference | State |
|---|---|---|---|
| Theory of operation | 29 | §4.5.4 | text |
| Test points (A5 TP1 "15V, 22 PPS square wave", etc.) | 38 | Table 5.1 | text |
| D/A converter adjustment procedure | 37 | §5.3.6 | text |
| Troubleshooting (U7, U8, K1/K3 failure modes) | ~55 | Table 5.2 | text |
| Parts list (complete) | 96–98 | Table 6.2 | text, readable OCR |
| Parts location index | 144 | — | text |
| **Schematic** | 145 | Fig. 7.11 (7.23/7.24) | **legible but partial; see below** |
| Assembly drawing (component placement) | 146 | Fig. 7.12 | image |
| Printed wiring, circuit side (copper) | 147 | Fig. 7.13 sheet 1 | image |
| Printed wiring, component side (copper) | 148 | Fig. 7.13 sheet 2 | image |

### Schematic legibility
- At 300 dpi the part numbers and most pin numbers read clearly: U4/U5 MM54C193J, U11 LM555N, U6 MC14075BAL, U7 REF-01, U8 DAC, R14 51K, R15 68K, C11, C12.
- Fine print (supply labels, some U8 pin labels, a few values) is faded.

### Gap: the fold-out is only partly in the scan
- The schematic shows grid columns **3–8 only**. Columns 1–2 are cut off, with signal lines running off the left edge. They likely hold the edge-connector pins and the input logic (U1 MC14490, parts of U2/U3).
- Mitigation: the scan includes the **assembly drawing and both copper layers**, so the missing connectivity can be rebuilt from the board artwork plus the parts list.
- This makes it a realistic "incomplete technical data package" case. It also means the hand-built reference netlist needs the artwork, not just the schematic.

## Bill of materials (Table 6.2)
- **ICs:**
  - U1 MC14490EFL hex contact-bounce eliminator
  - U2 MM54C10J triple 3-input NAND
  - U3 MM54C30J 8-input NAND
  - U4, U5 MM54C193J synchronous 4-bit up/down counters
  - U6 MC14075BAL 3-input OR
  - U7 REF01J +10 V precision reference
  - U8 DAC-08Q 8-bit multiplying D/A converter
  - U9 DC/DC converter (Burr-Brown 700, manufacturer code 13919)
  - U10 transformer-coupled isolation amplifier (Burr-Brown 3451)
  - U11 LM555 timer
- **Relays:** K1 DPDT (FC-210-13); K3–K5 SPDT TO-5 (Teledyne 411D-26); K2 not used.
- **Diodes:** CR1 1N914B; CR2/CR3 1N4746 18 V Zener.
- **Resistors:** R1–R15, including military-spec RN60C metal film and carbon composition; R12 is a 50K potentiometer.
- **Capacitors:** C1–C12, metal polycarbonate and tantalum.
- **Test points:** TP1–TP7 turrets.
- **Count:** about 50 components. It's mixed-signal: CMOS logic, a counter-driven DAC, a precision reference, an isolation amplifier, relays.

### Obsolescence (initial view, to be confirmed in Milestone 4)
- **Likely obsolete:**
  - MC14490 bounce eliminator
  - National MM54C-series logic
  - DAC-08Q (ceramic military grade)
  - REF01J
  - Burr-Brown 3451 and 700 modules
  - MC14075BAL ceramic
  - the Teledyne TO-5 relays (possibly still made)
- **Likely still available:** LM555, 1N914B, 1N4746, RN60C resistors.

## Bench-test notes
- The card drives relays and solenoids. Use a current-limited supply; the system runs from 28 V, and the card has ±15 V and +5 V rails.
- No surplus unit has been found yet.

## Next steps
1. Run `refit intake` on this manual with a live model. The text layer routes to transcription; confirm the statement in review.
2. Hand-build the reference netlist in KiCad from Fig. 7.11, then fill in columns 1–2 from Figs 7.12 and 7.13 and the parts list.
3. Plan Milestone 3 (parts list + schematic extraction) around this manual. The parts-list OCR is good; the schematic needs image-based extraction.
