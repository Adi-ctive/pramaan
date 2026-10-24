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

const fmtDate = (v: any) => {
  const m = String(v ?? "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return String(v ?? "");
  return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
};

const room = (t: string) => { const r = (t.split(":")[0] || "").replace(/_/g, " ").toLowerCase(); return r.charAt(0).toUpperCase() + r.slice(1); };

/** "Should be" and "Found" in plain words, or null when a comparison would not help. */
export function compare(f: any): [string, string] | null {
  const rec = (f.evidence || []).find((e: any) => e.type === "record")?.value;
  switch (f.code) {
    case "DOC_EXPIRED": return ["Valid on the day of submission", `Expired ${fmtDate(f.observed)}`];
    case "DOC_MISSING": return ["Uploaded", "Not uploaded"];
    case "INTAKE_MISMATCH_RECORDS": return [`${rec ?? "?"} students (AICTE approved)`, `${f.observed} students claimed`];
    case "NAME_MISMATCH": return [String(f.expected), String(f.observed)];
    case "INFRA_SHORTFALL": return [`${f.expected} computers`, `${f.observed} seen in photos`];
    case "AREA_SHORTFALL": return [`${f.expected} m²`, `${f.observed} m² on the plan`];
    case "FACULTY_COUNT_MISMATCH": return [`${f.expected} faculty (AICTE records)`, `${f.observed} listed`];
    case "EXIF_LOCATION_MISMATCH": return ["Taken on campus", `Taken ${f.observed} away`];
    case "FORMAT_INVALID": return ["Issuer's reference format", String(f.observed)];
    case "DATE_IMPLAUSIBLE": return [String(f.expected).replace(/^Issue date /, "Issued "), fmtDate(f.observed)];
    case "WRONG_DOC_TYPE": return [String(f.expected).replace(/_/g, " ").toLowerCase(), `a ${String(f.observed).replace(/_/g, " ").toLowerCase()}`];
    case "FEE_TOTAL_MISMATCH": return [`Items add up to ${f.expected}`, `Items add up to ${f.observed}`];
    default: return null;
  }
}

/** One plain sentence per finding, built from the finding's own data. Falls back to the engine's title. */
export function headline(f: any, docLabel: string): string {
  const ev = f.evidence || [];
  const field = (k: string) => ev.find((e: any) => e.type === "field" && e.key === k)?.value;
  const t: string = f.title || "";
  switch (f.code) {
    case "DOC_MISSING": return `${t.replace(" not uploaded", "")} was not uploaded`;
    case "DOC_EXPIRED": return `${docLabel} expired on ${fmtDate(f.observed)}`;
    case "WRONG_DOC_TYPE": return `Wrong document in the ${docLabel} slot`;
    case "NAME_MISMATCH": {
      const m = (f.reason || "").match(/'(.+?)' vs '(.+?)'/);
      return m ? `Name differs: “${m[1]}” vs “${m[2]}”` : "Names don't match across documents";
    }
    case "INTAKE_MISMATCH_RECORDS": return `Claims ${f.observed} students, AICTE approved ${ev.find((e: any) => e.type === "record")?.value ?? "fewer"}`;
    case "TAMPER_INDICATOR": return `Part of the ${docLabel} looks edited`;
    case "PDF_EDIT_INDICATOR": return `${docLabel} PDF was changed after it was created`;
    case "PDF_MODIFIED_AFTER_SIGNING": return `${docLabel} was changed after the issuer signed it`;
    case "PDF_SIGNATURE_INVALID": return `${docLabel} signature doesn't check out`;
    case "QR_MISMATCH": {
      const m = (f.reason || "").match(/(\w+): source '(.+?)' vs document '(.+?)'/);
      return m ? `QR code says “${m[2]}”, document says “${m[3]}”` : `${docLabel} QR code doesn't match the document`;
    }
    case "QR_SIGNATURE_INVALID": return `${docLabel} QR code is not signed by the issuer`;
    case "REF_MISMATCH": return `Issuing office's record differs from the ${docLabel}`;
    case "REF_NOT_FOUND": return `Issuing office has no record of this ${docLabel}`;
    case "VERIFICATION_SOURCE_UNAVAILABLE": return `Issuing office didn't respond. Confirm the ${docLabel} by hand`;
    case "DUPLICATE_ACROSS_INSTITUTIONS": return "This image also appears in another college's application";
    case "DUPLICATE_WITHIN_APPLICATION": return "The same image was uploaded twice";
    case "INFRA_SHORTFALL": return `${room(t)}: ${f.observed} computers seen in photos, ${f.expected} claimed`;
    case "AREA_SHORTFALL": return `${room(t)} is ${f.observed} m² on the floor plan, ${f.expected} m² claimed`;
    case "EXIF_LOCATION_MISMATCH": return `Photo was taken ${f.observed} from campus`;
    case "EXIF_MISSING": return "Photo has no location data";
    case "HTR_LOW_CONFIDENCE": return t.includes("scanned or handwritten") ? `${docLabel} is handwritten. A person needs to read it` : `Couldn't read “${(t.match(/'(.+?)'/) || [, "a field"])[1]}” clearly. A person should check`;
    case "INJECTION_INDICATOR": return `${docLabel} contains hidden text aimed at the AI`;
    case "FIELD_MISSING": return t.replace(/^.*?: /, `${docLabel}: `);
    case "FORMAT_INVALID": return `${docLabel} reference number looks wrong (${f.observed})`;
    case "DATE_IMPLAUSIBLE": return `${docLabel} date doesn't make sense (${fmtDate(f.observed)})`;
    case "VALIDITY_TOO_LONG": return `${docLabel} is valid for longer than the issuer allows`;
    case "FEE_SHORT": return `Fee paid is less than required (${f.observed})`;
    case "FEE_TOTAL_MISMATCH": return "Fee receipt items don't add up to the total";
    case "FACULTY_COUNT_MISMATCH": return `Faculty list has ${f.observed} people, AICTE records show ${f.expected}`;
    case "REQUIRED_REGION_MISSING": return `${docLabel} has no ${(t.match(/no (\w+) found/) || [, "seal or signature"])[1]}`;
    case "ROOM_TYPE_MISMATCH": return t.replace(/^[A-Z_0-9]+: /, "");
    case "MEDIA_NOT_ANALYSED": return "Video needs to be watched by a person";
    case "FLOOR_PLAN_NOT_MEASURED": return "Floor plan couldn't be measured automatically";
    default: return t;
  }
  void field;
}

/** What the officer should do, in one short line. */
export function nextStep(f: any): string {
  return f.recommended_action || ({ TAMPER_INDICATOR: "Ask for the original or check with the issuer",
    DUPLICATE_ACROSS_INSTITUTIONS: "Ask for fresh photos; consider an inspection", HTR_LOW_CONFIDENCE: "Read it yourself and confirm",
    INJECTION_INDICATOR: "No action needed. It was ignored. Note it for the record" } as Record<string, string>)[f.code] || "Decide whether this is a real problem";
}
