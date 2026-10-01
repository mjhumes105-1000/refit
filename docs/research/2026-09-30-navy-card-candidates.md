# Navy demo card candidates

Research pass, 2026-09-30. The fetch budget is used up, so the search stopped there. Unless marked otherwise, everything here comes from my own reading of the documents' PDF text layers (archive.org mirrors of DTIC scans, extracted with pdftotext). The OCR is imperfect, so every quote and part number needs a visual check against the page images before intake.

Hard requirement: Distribution Statement A, or the older "approved for public release; distribution is unlimited" (or "... and sale; its distribution is unlimited"), printed on the document itself.

## Recommendation

Use **card A5, "Searchlight Control Card I", from the US Coast Guard Model 066 Searchlight Positioner** (DTIC AD-A139850, 2 May 1983) as the Navy demo card.

- **Statement:** I read it myself. The cover and title page both carry "approved for public release and sale; its distribution is unlimited", which the REFIT gate now accepts.
- **Documentation:** the manual covers this one card with a schematic, an assembly drawing, a printed-wiring drawing, theory of operation, a test-point table and a parts list with Mil numbers.
- **Fit:** about 55 parts, and genuinely mixed-signal: 54C-series mil-temp CMOS counters and gates, a DAC-08 multiplying DAC, a REF01 reference, a 555-type timer and an op-amp stage.

**Weaknesses:**
- No surplus source is likely.
- The card switches relays and 28 V stow solenoids, so bench-test it from a current-limited 28 V supply.

Card A6 from the same manual is the fallback. It is relay-heavy and has about 105 parts.

The only other verified Navy-sourced card is an anonymous naval-weapons CCA in a NOS Louisville thesis (AD-A177074). The card can't be identified, so it is useful only as extra test material.

I did **not** reach 3 independent verified sources within the budget.

## Ranked candidates

| # | Card | Equipment and Navy use | Document, date, URL | Statement (as printed) and location | Criterion-1 elements | Components | Obsolete parts | Surplus | Risk |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Model 066 Searchlight Positioner, card A5 "Searchlight Control Card I"** (Contraves Goerz P/N 703711-1, per Table 6.2) | USCG shipboard searchlight positioner: a two-axis servo mount for the AN/VSS-3A searchlight, bought under Coast Guard contract DTCG23-83-C-40007, CG 7610-01-GF2-0201. Coast Guard counts as Navy under the brief | DTIC AD-A139850, *Technical Manual for Model 066 Searchlight Positioner*, effective 2 May 1983. [archive.org](https://archive.org/details/DTIC_ADA139850) | "This document has been approved for public release and sale; its distribution is unlimited." Stamped on the cover and repeated on the title page under "EFFECTIVE DATE: 2 MAY 1983". **Read by me** from the PDF text layer (OCR slightly garbled; wording reconstructed from two copies) | Schematic Fig. 7.11; assembly (component location) drawing Fig. 7.12; printed wiring Fig. 7.13 (2 sheets); theory of operation §4.5.4 (pp. 4.5–4.6); D/A converter adjustment §5.3.6; test-point table Table 5.1 (e.g. "A5 TP1 15V, 22 PPS square wave"); parts list Table 6.2, pp. 6.24–6.26, with reference designators, FSCM codes and Mil numbers | About 55 (C1–C12, CR1–CR3, K1–K5, R1–R15, TP1–TP7, U1–U11) | MC14490 hex bounce eliminator, MM54C10 and MM54C30 NAND gates, 2× MM54C193 up/down counters, MC14075 OR, REF01 precision reference, DAC-08Q 8-bit multiplying DAC, a 555-type timer (U11), a transformer-coupled amplifier (U10), a DC/DC converter module (U9), TO-5 relays. Mil-temp 54C CMOS | None found. Expect none: a USCG cutter item | Relays and 28 V stow-solenoid drive, so feed it a current-limited 28 V supply. OCR of the part numbers needs a visual check. Previous shortlist rank 2 |
| 2 | Model 066, card A6 "Searchlight Control Card II" (P/N 703712-1) | Same as #1 | Same as #1 | Same as #1 | Schematic Fig. 7.14 (2 sheets); assembly Fig. 7.15; printed wiring Fig. 7.16 (the list of illustrations numbers these 7.16–7.18, so check); theory §4.5.5; Table 5.1; parts list Table 6.2, pp. 6.27–6.30 | About 105 (C1–C6, CR1–CR24, K1–K13, Q1–Q3, R1–R43, TP1–TP9, U1–U6) | 3× LM148 quad 741, MM74C221 dual one-shot, MM54C08 AND, MM54C76 dual JK, VN66AK VMOS FETs | None | Relay-heavy and slightly above 100 parts. Logic is mostly relay sequencing |
| 3 | Unnamed low-frequency analog/logic CCA (signals VBMT, IFKT, IFMT; connector P2) | A CCA from "a complex naval weapons system" overhauled at Naval Ordnance Station Louisville, which has about 80 such analog cards. NAVSEA Acceptance Test Requirement reproduced as App. A | DTIC AD-A177074, "Automated Testing and Fault Isolation of a Low Frequency Analog Circuit Card Assembly", M. D. Pilkenton, Univ. of Louisville M.S. thesis under a US Navy contract with NOS Louisville, 17 Sep 1986. [archive.org](https://archive.org/details/DTIC_ADA177074) | A stamp on the thesis approval page. OCR reads "...disuibulion isiunlimited", which is consistent with the Statement A stamp but is garbled. **Confirm visually.** | Schematic in two parts (Figs 21–23, pp. 148–149); parts layout (p. 150) plus four computer-generated layout quadrants (pp. 151–154); full circuit analysis by sub-circuit (Ch. III); per-test expected voltages from the NAVSEA test requirement (App. A); fault-isolation flowcharts (Figs 37–56). **No parts list with part numbers found.** | Large: designators run to U25, Q49, CR25, so roughly 100–150 parts | 747 dual op amps (U20–U22), 555 timers (U1, U2, U3, U25), TTL output stages, 2N2222A (Q24, Q25). Supplies: +28 V, +5 V, −5 V | None. The host system is not named, so the card cannot be identified for purchase | Card identity unknown. Probably above the 100-part ceiling. Thesis, not an official manual |

## Checked and excluded

- **DTIC AD-A139851** (USCG Model 066A Searchlight Positioner, Contraves Goerz, 2 May 1983, contract DTCG23-83-C-40007). Read from the PDF text layer. No public-release statement was found anywhere in the OCR text (cover, DTIC header, body). The appendix also reproduces copyrighted National Semiconductor data sheets. Otherwise the documentation is excellent: A1–A6 cards; schematics Figs 7.3–7.13; parts list Table 6.2 with Mil numbers (LM101AH, LM108AH, 2N2219A, LM148N, MC14490, DAC-08, RN60 resistors); test points Table 5.1. Use the AD-A139850 (Model 066) version instead, which carries the statement.
- **DTIC AD-A129738** (Portable Duress Sensor, Sonicraft, 1983). Prepared for the US Army Mobility Equipment R&D Command, Fort Belvoir. Not Navy equipment.
- **DTIC AD-A189003** (NORDA Vertical Profiler O&M manual, Naval Ocean R&D Activity, July 1981). No public-release statement was found in the OCR text. The electronics are documented only by reference to the contractor's drawings (C & M Systems Dwg. D-1850-1) and wire-wrap boards, with no in-document card schematic or parts list.
- DTIC AD-A088593 (SES wave profiling system, JHU/APL, 1980). 14 MB, so not opened. Research instrumentation, not a fielded card.
- DTIC AD-A237277 (DCASP, 1988). Custom CMOS chip research, not a fielded card.
- DTIC AD-A085989 (NOSC microcomputer ASV system, 1979). Lab chemistry instrument, not fielded Navy equipment.

## Not verified / not checked

- apps.dtic.mil PDFs return HTTP 403 to WebFetch. Only the archive.org mirrors work.
- AD-A139850 was the previous shortlist's rank 2. I confirmed its statement and the A5/A6 card data myself in this pass. The figure numbers for A6 conflict between the list of illustrations (7.16–7.18) and the body text (7.14), so check them visually.
- AD-A177074: the Statement A stamp is inferred from garbled OCR ("disuibulion isiunlimited"). It must be confirmed on the page image.
- Model 066 cards A1/A2 (AZ and EL demodulators; LM101AH, LM108AH, 2N2219A, analog switch) and A3/A4 (input amplifier and notch filter, with relays) are also documented (schematics Figs 7.3–7.10, Table 6.2, Table 5.1). They are purely analog, with no logic, so they rank below A5.
- Surplus: not searched for any candidate.
- Leads not opened (fetch budget exhausted): AD-A167840 (Draw-Off Holdback control console, Western Gear, 1982); AD-A036314 (Towed Body Motion Measurement System, 1966); AD-A226813 (Diver Lift System, 1988); AD-A431392 (Supervisory Control System, 2005); TM 11-5820-401-34-2-1 / NAVELEX 0967-LP-432-3030 (AN/VRC-12 family, joint Army/Navy, 1984).
- TM 11-6625-2718-14&P (AN/URM-182). The radionerds PDF is image-only with no text layer, so it could not be read.
