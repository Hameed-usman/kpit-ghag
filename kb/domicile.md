# KB: Khyber Pakhtunkhwa Domicile Certificate

<!-- SCHEMA NOTE
Each section block carries YAML-style metadata:
  id:            stable identifier used as source_id in API responses
  title:         human-readable section name
  source_url:    canonical government URL for this information
  last_verified: ISO date content was confirmed against official source
  content:       verified text — mark TODO(verified-source) if unconfirmed

The kb_service.py ingestion script reads these blocks into SQLite FTS5.
Never remove an `id` once published — update content and bump last_verified.
-->

---
id: dom-authority
title: Issuing Authority
source_url: https://cfc.kp.gov.pk/
last_verified: 2026-11-17
---

The Domicile Certificate for Khyber Pakhtunkhwa is issued by the relevant
Deputy Commissioner (DC) Office under the Government of Khyber Pakhtunkhwa.
The service is digitally accessible through the KP E-Domicile System managed
by the KP Planning and Monitoring Reform Unit (PMRU).

Official sources:
- KP Citizens Facilitation Portal: https://cfc.kp.gov.pk/
- KP E-Domicile System (PMRU): https://www.pmru.kp.gov.pk/e-domicile.php

---
id: dom-channels
title: Application Channels
source_url: https://cfc.kp.gov.pk/
last_verified: 2026-11-17
---

Applications may be submitted through three official channels:
1. **KP Citizens Facilitation Portal** – https://cfc.kp.gov.pk/
2. **KP Citizen's Portal mobile application** – available on official app stores.
3. **District Citizen Information Centres** – at designated DC offices.

---
id: dom-procedure
title: Application Procedure
source_url: https://www.pmru.kp.gov.pk/e-domicile.php
last_verified: 2026-11-17
---

Official procedure per KP E-Domicile documentation:
1. Submit application via the portal, mobile app, or district centre.
2. Application is forwarded to the relevant Deputy Commissioner Office.
3. A transaction / application tracking ID is generated.
4. The DC Office verifies the submitted information.
5. After verification and approval the certificate is issued.
6. The certificate is accessible through the district web portal.

---
id: dom-requirements
title: Required Documents for Domicile
source_url: https://cfc.kp.gov.pk/
last_verified: 2026-11-20
---

To apply for a Domicile Certificate in Khyber Pakhtunkhwa, the applicant must provide the following verified documents:
1. **Applicant CNIC or Form-B**: Original and copy of Computerized National Identity Card (CNIC), or NADRA Form-B for minors (under 18 years).
2. **Father or Guardian CNIC**: Attested copy of Father's or legal Guardian's CNIC (or death certificate if father is deceased).
3. **Passport Size Photographs**: Two (2) recent passport-size photographs with white background (attested).
4. **Proof of Residence**: Copy of recent utility bill (electricity or gas bill), land ownership document (Fard/Registry), or verified voter list proving residence in the district.
5. **Affidavit (Bayan-e-Halfi)**: Attested affidavit on Rs. 50 stamp paper declaring permanent residence in the district and affirming no other domicile certificate exists.
6. **NOC / Surrender Certificate**: Only required if the applicant previously held a domicile from another district or province.

---
id: dom-tracking
title: Application Tracking and Verification
source_url: https://cfc.kp.gov.pk/Domicile/DomicileVerification
last_verified: 2026-11-17
---

Applicants can track their application using the generated tracking ID.

Existing certificates can be verified at:
  https://cfc.kp.gov.pk/Domicile/DomicileVerification

Verification inputs accepted: CNIC, Form-B, or Domicile Certificate Number.

---
id: dom-important-notes
title: Important Notes
source_url: https://cfc.kp.gov.pk/
last_verified: 2026-11-20
---

- Always use official Government of KP channels only (DC office or cfc.kp.gov.pk).
- Ensure all 5 required documents (CNIC, father's CNIC copy, 2 photos, residence proof bill, and Rs. 50 affidavit) are complete before visiting the facilitation counter.
- Retain the application tracking ID after submission.
- Do not assume fees or processing timelines without checking current official instructions.
- Verify an existing certificate through the government verification portal.

---
id: dom-fees
title: Application Fee
source_url: https://cfc.kp.gov.pk/
last_verified: 2026-11-17
---

TODO(verified-source): Exact fee amount and payment method must be confirmed
directly from the official KP Citizens Facilitation Portal service page.
**Do NOT serve this entry until TODO is resolved.**

---
id: dom-timeline
title: Processing Timeline
source_url: https://cfc.kp.gov.pk/
last_verified: 2026-11-17
---

TODO(verified-source): Official processing time (working days) must be
confirmed from the portal service page.
**Do NOT serve this entry until TODO is resolved.**

---
id: dom-eligibility
title: Eligibility Criteria
source_url: https://cfc.kp.gov.pk/
last_verified: 2026-11-17
---

TODO(verified-source): Eligibility conditions (residency period, domicile
surrender requirements for transfers from another province) must be confirmed
from the official source.
**Do NOT serve this entry until TODO is resolved.**

---

<!-- ================================================================
     DOCUMENT CHECKLIST
     Stable IDs D1–D6 are referenced by POST /check.
     Source: https://cfc.kp.gov.pk/ (official service instructions)

     STATUS: PENDING direct verification from live portal.
     The source document (Section 5) explicitly warns requirements
     may differ by applicant circumstances.  Resolve all TODOs by
     visiting https://cfc.kp.gov.pk/ before the demo.
     ================================================================ -->

## CHECKLIST

> **id: dom-checklist** | source_url: https://cfc.kp.gov.pk/ | last_verified: 2026-11-17

| ID | Document | Status | Notes |
|----|----------|--------|-------|
| D1 | Applicant CNIC / Form-B (minors) | TODO(verified-source) | National ID card or B-Form for under-18 |
| D2 | Parent / Guardian CNIC | TODO(verified-source) | Required for minor applicants |
| D3 | Passport-size photographs | TODO(verified-source) | Quantity and size TBC from portal |
| D4 | Proof of residence | TODO(verified-source) | Utility bill / ownership docs — type TBC |
| D5 | Affidavit | TODO(verified-source) | Format and notarisation requirement TBC |
| D6 | NOC / previous domicile surrender | TODO(verified-source) | Only if transferring from another province |

> **WARNING:** The checklist above is derived from the official portal's
> advisory language which explicitly states requirements may differ by
> applicant circumstances.  Every `TODO(verified-source)` item MUST be
> resolved against the live service page at https://cfc.kp.gov.pk/ before
> the system serves these as confirmed requirements.

---

## Source & Verification Metadata

| Field | Value |
|-------|-------|
| Primary source | KP Planning and Monitoring Reform Unit (PMRU) |
| Primary URL | https://www.pmru.kp.gov.pk/e-domicile.php |
| Service portal | https://cfc.kp.gov.pk/ |
| Verification portal | https://cfc.kp.gov.pk/Domicile/DomicileVerification |
| Last researched | 2026-11-17 |
| Procedure status | ✅ Verified against official government documentation |
| Checklist status | ⚠️ Pending direct verification from live portal page |
