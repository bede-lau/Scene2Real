# Historical IRS worksheet: source notes

This is preparation for a clearly labelled **historical Incident Recording System (IRS) worksheet** with unsupported information left blank. It is not the current England FaRDaP form, a complete specification of the 2012 IRS, a validated submission, or an official document. Further product/design approval is pending. No Scene2Real run field has been mapped to a historical question in this inventory.

`historical-worksheet-fields.json` reproduces the 158 numbered question entries from `historical-question-index.csv`, preserving the table-of-contents order across nine sections, the whitespace-normalized contents labels, historical IDs, and printed, PDF and contents-page references. The original source is the unmodified `historical-irs-questions-v1.6.pdf`; source URL, Crown copyright attribution and hash are in the JSON and `sources.json`. A contents label is a navigation aid: it is not proof that a single visible input, its allowed answer values or its dependencies have been fully represented. The printed-page reference denotes the beginning of the question in the source, not necessarily the complete table.

## Representative source table review

The following entries were checked against the full relevant question tables, including continuations where needed. Printed pages and one-based PDF pages refer to the 2012 PDF. These are observations about that historical source, not proposed field types, conditional rules or current requirements.

- **1.1 — FRS Incident Number** (printed 20; PDF 24): the table identifies an FRS incident number; it is not a Scene2Real run identifier.
- **2.1 — What was the time and date of call?** (printed 24; PDF 28): the note refers to when the call was received. Clip-relative sample times and report generation time do not establish it.
- **3.1 — incident category** (printed 28; PDF 32): the table describes incident categorisation and says it determines further questions. The index alone does not capture that branching.
- **4.2* — Location Address** (printed 34; PDF 38): the asterisk entry is a contents-level grouping. The source displays subfields 4.2a–4.2g and describes dependencies among them. It is not evidence that `4.2*` is a single technical field, and an authored warehouse zone is not an address.
- **5.1 — Did the fire have multiple seats?** (printed 36; PDF 40): the historical question concerns fire seats, with a context note. Counts of image detections across views do not establish the number of seats.
- **6.2 — information known about FRS vehicles** (printed 50–52; PDF 54–56): the broad contents label accompanies a historical vehicle-type list. Vehicle information may be repeating; a robot or a simulated vehicle cannot be equated to an attending FRS appliance.
- **7.3 — main action taken by FRS personnel** (printed 62–63; PDF 66–67): the table is explicitly about actions by FRS personnel. A modelled robot action does not establish such an action.
- **8.1 — cause of the fire** (printed 69–71; PDF 73–75): the historical source filters its cause list based on question 5.15. An observation of flames is not an established cause.
- **9.1 — people evacuated without assistance** (printed 95; PDF 99): the surrounding section describes persons and applicability. Missing person evidence does not mean an evacuation count of zero.

The 4.3a/b and 6.14a & b identifiers also group subfields in the historical contents. The index deliberately retains these strings; it does not expand them into guessed inputs. The contents include unnumbered hidden, derived or callsign items beyond the 158 numbered entries. They are not silently treated as covered by the inventory.

## Limitations and provenance

The historical PDF's cover/footer refer to XML schema v1-0p while its inner title says v1-0n. Its printed page 9 (PDF 13) says companion technical/schema documents are definitive for business rules and that the publication itself omits many of the 200-plus rules. The inventory has no guessed field types, options, default values, required states, conditional rules or mappings. Blank values in a draft must not be interpreted as a completed valid historical or current submission.

MHCLG says that FaRDaP succeeded IRS and that the transition to FaRDaP v2 changes questions and options. The exact active FaRDaP version, authorised question dictionary, templates, schemas, enumerations and validations require confirmation with MHCLG or the participating fire and rescue service before any current-standard claim. See `national-standard.md` for sources and evidence boundaries.
