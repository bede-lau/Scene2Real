# DRAFT ONLY — DO NOT SEND

Status: prepared by Devin on 2026-10-19. **Not sent. User declined sending on 2026-10-19: “No, don't send the inquiry”. Do not send.** Retained as a local reference only.

Routing: `firestatistics@communities.gov.uk` is the public statistics enquiry address listed on [Fire stations dataset guidance](https://www.gov.uk/government/statistics/fire-statistics-incident-level-datasets/fire-stations-dataset-guidance). It is **not confirmed** as the FaRDaP developer-access desk; the message asks to be redirected. Parallel route: a participating English fire and rescue service's information/data team (D1 in the implementation plan — service not yet chosen).

Before sending, the user should check: no incident, personal or credential data is attached; the placeholders are filled truthfully; the stated purpose matches what they intend to build.

---

**To:** firestatistics@communities.gov.uk
**Subject:** Request for current FaRDaP incident-recording specification (developer access) — Scene2Real preparation tool

Dear Fire Statistics team,

I am developing Scene2Real, a tool intended to help English fire and rescue personnel prepare a draft incident record from reviewed video evidence. The tool would never submit records itself and would leave every field blank unless an authorised officer enters or explicitly accepts a value. To avoid presenting outdated or invented questions, I would like to build only from the current authorised specification.

Your fire and rescue incident statistics publication states that incident data have been collected through the Fire and Rescue Data Platform (FaRDaP) since November 2025, and that a transition to FaRDaP v2 is planned to begin in autumn/winter 2026. The public FaRDaP GitHub organisation (https://github.com/HO-FaRDaP) refers to a private developer-resources repository. The only detailed public material I have found is the 2012 IRS *Questions and Lists v1.6*, which I am treating as historical only.

If this inbox is not the right route, I would be grateful if you could forward this message or tell me the correct contact for FaRDaP developer access.

Could you please tell me, or provide where permitted:

1. **Active version and applicability.** Which FaRDaP version(s) services are using now, the planned v2 timetable, whether services move on different dates, and how a service's active version can be identified.
2. **Field dictionary.** Questions/fields with identifiers, labels, definitions, data types, units, formats and ordering, for each active version.
3. **Technical schema.** Any XSD, JSON Schema, API specification or file interface used for FaRDaP submission or exchange, with version identifiers.
4. **Code lists.** All enumerations/answer options with codes, labels and ordering, including how "not known", "not applicable", "none" and zero are represented and when each is permitted.
5. **Business rules.** Mandatory, conditional, repeating-group and cross-field validation rules, including how fields are shown or hidden by earlier answers and how bespoke service systems are expected to apply them.
6. **Printable / downloadable output.** Whether a national printable or downloadable incident-record template exists. If services use their own layouts, please say so; I would not want to imply that a single universal form exists if it does not.
7. **Sample and validation pack.** Synthetic example records, expected validation results or a conformance test set, if available.
8. **Release history.** Change logs or release notes between versions, especially IRS → FaRDaP v1 → v2.
9. **Reuse terms.** The licence or terms under which these materials may be used in a non-submitting preparation tool, including any restrictions on redistributing them.
10. **Developer access process.** How to request access to the FaRDaP developer resources, any eligibility criteria (for example, sponsorship by a fire and rescue service), and any security or data-handling conditions.

I am **not** requesting any incident-level, personal or service-identifying operational data. Synthetic or blank examples are all I need.

Thank you for your help.

Kind regards,
[Name]
[Role / organisation]
[Contact email]
[Optional: participating fire and rescue service contact, if any]

---

## Variant for a participating fire and rescue service (also DRAFT, not sent)

Same body, with these changes:
- Address the service's information/data or incident-recording team ([contact to be identified by the user]).
- Replace the routing paragraph with: "If FaRDaP developer materials must be requested by a service rather than an individual, would your service be willing to sponsor or advise on that request?"
- Add to item 1: "Which FaRDaP version and recording system your service uses, and whether you record through the national platform or a bespoke system."
- Add to item 6: "If your service uses its own printable incident record, may I see a blank copy and its field mapping to FaRDaP?"
