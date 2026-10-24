# England fire and rescue incident reporting: source pack

Research checked 19 October 2026. This is a source and mapping aid, not an approved incident form, submission schema or an assertion of compliance. The 2012 IRS material is historical. Do not present its question set or layout as the current FaRDaP form.

## National collection and version

[MHCLG’s fire and rescue incident statistics, year ending March 2026](https://www.gov.uk/government/statistics/fire-and-rescue-incident-statistics-year-ending-march-2026/fire-and-rescue-incident-statistics-year-ending-march-2026--2) says incident data were collected through the Incident Recording System (IRS) until November 2025 and subsequently through the Fire and Rescue Data Platform (FaRDaP). The release says fire and rescue services (FRSs) record each attended incident, including fires, false alarms and non-fire incidents. It says the transition to FaRDaP v2 is to begin in autumn/winter 2026, with additions and changes to questions and answer options. This schedule does not establish which version an individual service currently uses.

The [methodology and quality report](https://www.gov.uk/government/publications/fire-statistics-guidance/fire-and-rescue-incident-statistics-methodology-and-quality-report) describes a shared question set and guidance while some services use bespoke systems. Its QA section describes the historical IRS workflow, applicability checks, date ordering, approved options and service review; it must not be treated as a specification of the current FaRDaP workflow. The [MHCLG FaRDaP GitHub organisation](https://github.com/HO-FaRDaP) says its developer resources are in a private repository. Public access to its full current question dictionary, schema and form was not established by these sources.

## Historical reference only

[Incident Recording System – Questions and Lists, Version 1.6, from April 2012](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/974650/incident-recording-system-questions-and-lists-version-1.6-XML-Schemas-v1-0p-from-April-2012.pdf), Department for Communities and Local Government, July 2012, © Crown copyright, is saved unchanged as `historical-irs-questions-v1.6.pdf`. Its cover and footer identify XML schemas v1-0p, while the inner title page says v1-0n; preserve this discrepancy rather than silently resolving it. The source’s printed page 9 (PDF page 13) says companion technical/schema documents definitively describe the business rules and that this publication does not contain all 200-plus rules. Question tables begin on printed page 19 (PDF page 23); they describe formats, conditions and notes for that historical version.

`historical-question-index.csv` extracts the 158 numbered questions from the historical table of contents, with whitespace normalized. It records the question's printed starting page, the corresponding one-based PDF page (printed page + 4), and the one-based PDF table-of-contents page. It is a navigation index, not a field dictionary or a current-schema mapping. Unnumbered hidden/derived and callsign items also appear in the historical contents and are not counted as numbered questions. Nine historical sections cover Incident Identity, At Call Details, On Attendance Details, Location Details, Additional Information, Resources Used, Action, Damage and Involvement of Persons. Titles are indexed without inferring current mandatory status, options, conditionality, semantics or output layout.

The historic PDF states that its information may be reused under the Open Government Licence, excluding logos. The index attributes the source above; consult the licence and any third-party rights before redistribution or incorporating source material into a product.

## What is needed for an exact current form

Obtain the active version from MHCLG or the participating FRS, together with the authorised field dictionary, exact form/output template, technical schema and version, allowed enumerations, required/conditional rules, business validations, workflow and submission guidance. Establish service-specific applicability and version before implementing or claiming an exact match. Access to the private developer resources may be needed. A historical public document alone cannot establish a complete or valid current form.

## Evidence boundaries for Scene2Real

The existing app supplies machine-generated video observations and simulation outcomes, not established real-world fire service records or robot telemetry. Treat source provenance, timestamps and confidence as evidence for human review. Do not map clip-relative sample times to incident call, attendance, stop or closure clocks; do not map a simulation result to FRS action, real suppression or an extinguished fire; do not treat an authored template zone or coordinates as an incident address, measured location or fire origin; and do not convert missing casualty information into zero. An absent value is not proof of a negative.

Populate an official field only when its approved definition and a sufficiently supported source agree; leave unsupported values blank in a clearly marked draft for an authorised operator to complete and verify. A draft with blank required values is not a validated mandatory-field submission. No current FaRDaP field-level mapping or submission conformance can be verified from the public historical source alone.

## Verified route for obtaining the specification

MHCLG lists **firestatistics@communities.gov.uk** for public enquiries in its [Fire stations dataset guidance](https://www.gov.uk/government/statistics/fire-statistics-incident-level-datasets/fire-stations-dataset-guidance), updated 22 July 2026. This is a verified public-enquiries address, not a confirmed FaRDaP developer-access helpdesk. Ask it to route the request to the appropriate team. The public developer organisation does not publish an access application procedure.

Request existing non-personal specification materials and the access process, not real incident records or production credentials. Confirm which active version and service apply, and whether the national contract defines a printable form or whether that output is service-specific. A public enquiry does not guarantee access. A draft request will be reviewed separately; no enquiry has been sent.
