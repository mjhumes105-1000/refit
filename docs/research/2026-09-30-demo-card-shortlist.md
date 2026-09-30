# Demo card shortlist (Milestone 1)

Research pass, 2026-09-30. Hard requirement: **Distribution Statement A**, verified on the manual's own cover or title page. Candidates are ranked by fit with the spec's §8 criteria.

## Recommendation: AN/URM-206 Signal Generator, card 1A4 High Voltage Control Board (P/N C161321)

It is the only candidate where every documentation element was read directly, across two Distribution A manuals:
- a parts list with military part numbers
- a per-pin voltage and resistance table, which gives ground truth for the equivalence harness

The card itself runs at +32 V or less, and at about 60–70 parts it fits the size criterion. Its obsolete parts are a good mix: a military-grade 555, a 723 regulator, a 78M20, and power transistors.

**Weaknesses:**
- No 74-series TTL; the logic is 4000-series CMOS on neighbouring cards.
- No surplus units found.
- The host instrument has 1850 V klystron supplies, so bench-test the card on its own.

**Still to verify before committing:**
- The schematic and component-layout figure numbers (probably Fig. 5-3 and Fig. 4-13; the OCR was garbled).
- That the schematic is legible when rendered.

## Ranked candidates

| # | Card | Manual(s) | Statement (as printed) | Documentation found | Notes |
|---|---|---|---|---|---|
| 1 | AN/URM-206 (SG-1145/URM, Polarad 1108E-Y), card 1A4 HV Control Board C161321 | TM 11-6625-2948-14&P (28 Dec 1979, Change 2 dated 06 Jul 2006): [PDF](https://radionerds.com/images/6/60/TM_11-6625-2948-14&P.PDF) · TM 11-6625-2948-24P: [PDF](https://radionerds.com/images/e/ec/TM_11-6625-2948-24P.PDF) | "DISTRIBUTION STATEMENT A – Approved for public release; distribution is unlimited." Printed on the cover of both manuals and on the Change 2 cover. | Parts list (-24P Fig. 8, 46 line items with military part numbers), per-pin V/Ω table (Table 5-1), theory of operation (Ch. 3), troubleshooting chart. Schematic and layout appear in the list of illustrations. | Obsolete parts: M38510/10901BPB, SN72723, MC78M20CT, 2N5190, 2N4402, MJE3055T, MDA920A3, JAN1N4467, RCR/RNC/CMR passives. No TTL, no surplus found. |
| 2 | Coast Guard Model 066 Searchlight Positioner (Contraves Goerz), cards A1/A2 (demodulator) or A5 (control) | DTIC AD-A139850, 2 May 1983: [archive.org](https://archive.org/details/DTIC_ADA139850) | "approved for public release and sale; its distribution is unlimited" (older wording that means Statement A; no letter printed) | Schematics (Figs 7.3–7.20), parts lists (Tables 6.1–6.2), component location (Fig. 5.5), theory of operation (Ch. 4), test-point voltage and waveform table (Table 5.1), troubleshooting (Table 5.2) | Op-amps, logic, counters, D/A converter. Page details come from a summarizer, not a direct read. No surplus expected. |
| 3 | Test Set, Transistor TS-1836D/U, single board | TM 11-6625-539-14-4 (29 Aug 1975, Change 2 dated 28 Apr 2006): [PDF](https://www.radionerds.com/images/4/46/TM_11-6625-539-14-4.PDF) | "DISTRIBUTION STATEMENT A-Approved for public release; distribution is unlimited." | Schematic (FO-2), component location (Fig. 7-6), reference designator table (7-2), theory of operation (Ch. 5), waveform check. **No voltage tables; parts list is in a separate manual.** | About 82 parts (AR1–AR4, Z1, Q1–Q6). No TTL. |
| 4 | DEB Type I Alarm Status Unit (USAF/MITRE), boards 1–3 | ESD-TR-80-132, Aug 1980, DTIC AD-A089969: [archive.org](https://archive.org/details/DTIC_ADA089969) | "Approved for public release; distribution unlimited." | Theory of operation, schematics, parts list, maintenance tables. Component location from photos only. | Mostly TTL, a one-off unit, not Navy. |
| 5 | Solid State Readout Device (USAF AMD / SwRI) | DTIC AD-A041101, June 1975 | "Approved for public release; distribution unlimited." | Schematics, parts lists, component location, theory of operation, voltage-guided troubleshooting (summarizer) | Research prototype, no surplus. |

## Checked and excluded (not Distribution A, or unusable)

**Restricted distribution:**
- TM 11-6625-3165-14 (DoD and contractors)
- TM 11-6625-2858-14&P (DoD)
- TM 11-6625-3015-14 (DoD and contractors)
- TM 11-5821-318-30 (US Government, plus an arms-export warning)
- TM 11-5830-340-30 AN/VIC-1 (US Government)
- TM 11-6130-356-34 (DoD and contractors)

**Distributed per a DA form, not Statement A:**
- TM 11-6625-2697-14 (AN/USM-44C)

**No statement found:**
- TM 11-6625-2495-14&P
- TM 11-6625-3016-14
- TM 11-5820-919-40-1
- TM 11-6665-245-34
- TM 11-6625-700-25
- DTIC AD-A143864

**Copyright or proprietary legend:**
- TM 11-6625-2924-14&P (Tektronix)
- TM 11-6625-3152-14 (Tektronix)
- TM 11-5820-590-35-1 (Hughes)

**Distribution A, but no schematics or parts list:**
- DTIC AD-A114394

## Not yet checked
- **Over the 10 MB fetch limit:**
  - TM 11-6625-2578-34 (OQ-60/USQ-46)
  - TM 11-5840-211-35 (AN/PPS-4A)
- **Unverified leads:**
  - DTIC AD-A139851, AD-A129738 and AD-A310115
  - TM 3-6665 chemical-detector manuals
  - TM 11-6130-426-13&P
  - TM 11-5805 telephone manuals
  - The TS-1836 parts-list manual
- **Surplus availability:** unverified for every candidate.

## Gate note
Candidate 2's older wording, "approved for public release and sale; its distribution is unlimited", has no statement letter. REFIT's intake gate accepts "approved for public release … distribution is unlimited", but the words "and sale" sit between them. Check that the gate's public-release pattern matches this exact wording before running intake on candidate 2.
