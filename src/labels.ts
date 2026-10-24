// Plain-language names used across the console.

export const CATEGORY: Record<string, string> = {
  EOA: "Extension of Approval",
  AFFILIATION: "Continuation of Affiliation",
};

export const ROLES: Record<string, { name: string; does: string }> = {
  SENIOR_OFFICER: { name: "Senior Officer", does: "Sees every application and records the final decision note." },
  SCRUTINY_OFFICER: { name: "Scrutiny Officer", does: "Reviews applications in one region and confirms or dismisses findings." },
  RULE_ADMIN: { name: "Rule Admin", does: "Edits the checklist rules and runs the accuracy evaluation." },
  INTEGRATION_ADMIN: { name: "Integration Admin", does: "Connects portals, rotates API keys and watches webhooks." },
  AUDITOR: { name: "Auditor", does: "Read-only. Checks the tamper-proof audit trail." },
  INSTITUTION: { name: "Institution", does: "Uploads documents through a portal and sees only what to fix." },
};

// The checks every application goes through, and which finding codes fail each one.
export const CHECKS: { key: string; title: string; plain: string; codes: string[] }[] = [
  { key: "complete", title: "All documents uploaded", plain: "Every required document is present and in the right slot.", codes: ["DOC_MISSING", "WRONG_DOC_TYPE", "FIELD_MISSING"] },
  { key: "valid", title: "Documents are valid", plain: "Not expired, dates make sense, reference numbers look right.", codes: ["DOC_EXPIRED", "DATE_IMPLAUSIBLE", "VALIDITY_TOO_LONG", "FORMAT_INVALID"] },
  { key: "names", title: "Names match", plain: "The society and institution name is the same on every document.", codes: ["NAME_MISMATCH"] },
  { key: "records", title: "Matches AICTE records", plain: "Claims agree with what AICTE already holds (intake, fees).", codes: ["INTAKE_MISMATCH_RECORDS", "FEE_SHORT"] },
  { key: "tamper", title: "No signs of editing", plain: "No pasted-in text, edited PDFs or hidden instructions.", codes: ["TAMPER_INDICATOR", "PDF_EDIT_INDICATOR", "INJECTION_INDICATOR"] },
  { key: "issuer", title: "Confirmed with issuer", plain: "Signed QR codes and reference numbers checked with the issuing office.", codes: ["QR_MISMATCH", "QR_SIGNATURE_INVALID", "REF_MISMATCH", "REF_NOT_FOUND", "VERIFICATION_SOURCE_UNAVAILABLE"] },
  { key: "photos", title: "Photos are genuine", plain: "Photos are not reused from another college and were taken on campus.", codes: ["DUPLICATE_ACROSS_INSTITUTIONS", "DUPLICATE_WITHIN_APPLICATION", "EXIF_LOCATION_MISMATCH", "EXIF_MISSING"] },
  { key: "infra", title: "Facilities match claims", plain: "Equipment counted in lab photos matches what was claimed.", codes: ["INFRA_SHORTFALL", "INFRA_DETECTOR_UNAVAILABLE"] },
  { key: "read", title: "Readable by machine", plain: "Scanned or handwritten pages that a person must read.", codes: ["HTR_LOW_CONFIDENCE", "EXTRACTION_LOW_CONFIDENCE", "CHECK_ERROR"] },
];

export const CHECK_OF: Record<string, string> = Object.fromEntries(CHECKS.flatMap((c) => c.codes.map((code) => [code, c.title])));

export const SEVERITY_WORD: Record<string, string> = { HIGH: "Serious", MEDIUM: "Check", LOW: "Minor", INFO: "Info" };

export const DEMO_STEPS: { title: string; body: string; link?: string; linkText?: string }[] = [
  { title: "See the queue", body: "Applications arrive already checked. The worst ones are on top, so officers start where the problems are.", link: "/", linkText: "Open the queue" },
  { title: "Open the problem application", body: "Narmada College has 11 seeded problems: a missing certificate, an expired Fire NOC, a pasted-in date, a reused lab photo and more. Each finding points at the exact place on the document." },
  { title: "Compare with a clean one", body: "Shivalik Institute passes every check. All documents are verified with their issuers." },
  { title: "Upload as an institution", body: "Use the mock Approval Portal. Download the sample files, upload them, and the widget warns about problems instantly.", link: "/host-a/", linkText: "Open Approval Portal (mock)" },
  { title: "Fix and re-upload", body: "Upload the renewed Fire NOC. Only that document is re-checked, and the timeline shows it." },
  { title: "Same engine, another portal", body: "The University Affiliation Portal uses different slot names and a different rule pack. Nothing in the engine changes.", link: "/host-b/", linkText: "Open University Portal (mock)" },
  { title: "Decide", body: "The decision note stays locked until every serious finding has been confirmed or dismissed with a reason." },
  { title: "Prove nothing was changed", body: "The audit trail is hash-chained. Verify it, and any edited row breaks the chain.", link: "/audit", linkText: "Open audit" },
];
