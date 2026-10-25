import { AlertTriangle, ArrowLeft, Building2, Camera, Check, ChevronLeft, ChevronRight, ChevronDown, FileText, FileWarning, Flag, Lock,
  ShieldAlert, ShieldCheck, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Chip, VSTAT } from "../api";
import { useUser } from "../ctx";
import { CATEGORY, CHECKS, CHECK_OF, compare, headline, nextStep } from "../labels";
import { CHECK_ICON, Tour } from "../ui";

const ORDER = ["HIGH", "MEDIUM", "LOW", "INFO"];
const SEV = {
  HIGH: { word: "Serious", dot: "bg-red-500", ring: "border-red-300 dark:border-red-800", text: "text-red-600" },
  MEDIUM: { word: "Check", dot: "bg-amber-400", ring: "border-amber-300 dark:border-amber-800", text: "text-amber-600" },
  LOW: { word: "Minor", dot: "bg-sky-400", ring: "border-sky-200 dark:border-sky-800", text: "text-sky-600" },
  INFO: { word: "Info", dot: "bg-slate-400", ring: "border-slate-200", text: "text-slate-500" },
} as Record<string, any>;
const VWORD: Record<string, string> = {
  VERIFIED: "Confirmed", MISMATCH: "Does not match", SIGNATURE_INVALID: "Signature invalid", NOT_FOUND: "Not found at issuer",
  SOURCE_UNAVAILABLE: "Issuer did not respond", MANUAL_REVIEW: "Needs manual check", EXPIRED: "Expired",
};
const FORM = "FORM";

function boxOf(f: any, doc: any) {
  for (const e of f.evidence) if ((e.type === "region" || e.type === "field") && e.document_id === doc?.id && e.bbox && e.bbox[2] < 1) return e.bbox;
  if (f.code.startsWith("QR_") && doc?.qr) return doc.qr.bbox;
  return null;
}

function docOf(f: any) {
  return f.doc_id || f.evidence.find((e: any) => e.document_id)?.document_id || FORM;
}

export default function Detail() {
  const { id } = useParams();
  const user = useUser()!;
  const [d, setD] = useState<any>(null);
  const [idx, setIdx] = useState(0);
  const [docSel, setDocSel] = useState<string>("");
  const [check, setCheck] = useState("");
  const [reason, setReason] = useState("");
  const [act, setAct] = useState<string | null>(null);
  const [tech, setTech] = useState(false);
  const [heat, setHeat] = useState(true);
  const [more, setMore] = useState("");
  const [note, setNote] = useState("");
  const [obs, setObs] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => api(`/applications/${id}`).then(setD);
  const [health, setHealth] = useState<any>({});
  useEffect(() => { api("/health").then(setHealth).catch(() => {}); }, []);
  const req = d?.application?.agent_request;
  useEffect(() => {
    if (!req || !["pending", "running"].includes(req.status)) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [req?.status]);
  useEffect(() => { load(); }, [id]);

  const flags = useMemo(() => (d?.flags || []).slice().sort((a: any, b: any) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity)), [d]);
  const shown = check ? flags.filter((f: any) => CHECKS.find((c) => c.key === check)!.codes.includes(f.code)) : flags;
  const cur = shown[Math.min(idx, Math.max(0, shown.length - 1))];
  useEffect(() => { if (cur) { setDocSel(docOf(cur)); setAct(null); setReason(""); setTech(false); } }, [cur?.id]);

  if (!d) return <div className="text-sm text-slate-500 p-6">Loading application…</div>;
  const a = d.application, rep = d.report || {};
  const can = (c: string) => user.caps.includes(c);
  const docs = d.documents.filter((x: any) => !x.superseded);
  const label = (x: any) => (x === FORM ? "Application form" : d.taxonomy[x?.slot] || x?.slot);
  const docById = (did: string) => docs.find((x: any) => x.id === did) || d.documents.find((x: any) => x.id === did);
  const doc = docSel && docSel !== FORM ? docById(docSel) : null;
  const live = flags.filter((f: any) => f.status !== "DISMISSED");
  const nHigh = live.filter((f: any) => f.severity === "HIGH").length, nMed = live.filter((f: any) => f.severity === "MEDIUM").length;
  const reviewed = flags.filter((f: any) => f.status !== "OPEN").length;
  const highOpen = flags.filter((f: any) => f.severity === "HIGH" && f.status === "OPEN");
  const missing = d.required_slots.filter((s: string) => !docs.some((x: any) => x.slot === s));
  const pinFlags = doc ? shown.filter((f: any) => docOf(f) === doc.id) : [];
  const heatmap = doc?.images?.find((i: any) => i.heatmap)?.heatmap;
  const dup = cur?.evidence.find((e: any) => e.type === "duplicate" && e.other_pages?.length);
  const go = (i: number) => setIdx(Math.max(0, Math.min(shown.length - 1, i)));
  const dispose = async (action: string) => {
    try { await api(`/flags/${cur.id}/dispose`, { json: { action, reason } }); await load(); }
    catch (e: any) { setMsg(e.message); }
  };
  const decide = async () => {
    try { await api(`/applications/${id}/decision`, { json: { text: note } }); setMsg("Decision recorded."); load(); }
    catch (e: any) { setMsg(e.status === 409 ? `Still locked: ${e.body.open_high.length} serious problem(s) not reviewed.` : e.message); }
  };
  const docLabelOf = (f: any) => { const x = docOf(f); return x === FORM ? "Application form" : label(docById(x)); };
  const groups = [
    { title: "Documents", items: docs.filter((x: any) => x.slot !== "INFRA_PHOTOS") },
    { title: "Photos & videos", items: docs.filter((x: any) => x.slot === "INFRA_PHOTOS") },
  ];
  const Status = nHigh ? ShieldAlert : nMed ? AlertTriangle : ShieldCheck;

  return (
    <div className="space-y-5 pb-28">
      <Tour id="detail" steps={[
        { sel: "[data-tour=status]", text: "This is the verdict. Red means serious problems, green means every check passed." },
        { sel: "[data-tour=checks]", text: "The 9 things PRAMAAN checks. Click one to see only its problems." },
        { sel: "[data-tour=docs]", text: "Every document the college sent. A red number means problems were found in it." },
        { sel: "[data-tour=viewer]", text: "The document itself. Numbered pins show exactly where each problem is." },
        { sel: "[data-tour=problem]", text: "One problem at a time, in plain words. Decide if it's real, then go to the next one." },
        { sel: "[data-tour=decision]", text: "When every serious problem is reviewed, you can record the decision here." },
      ]} />

      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/" className="btn2 inline-flex items-center gap-1"><ArrowLeft size={16} /> All applications</Link>
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight truncate">{a.form.institution_name}</h1>
          <div className="text-sm text-slate-500">{CATEGORY[a.category] || a.category} · sent through {d.host}</div>
        </div>
        <div className="flex-1" />
        {health.local_ai?.online && can("dispose_flags") && (
          <button className="btn2 border-violet-300 text-violet-700 dark:text-violet-300" disabled={req && ["pending", "running"].includes(req.status)}
            onClick={async () => { await api(`/applications/${id}/run-local`, { method: "POST" }); load(); }}>
            {req?.status === "pending" ? "Waiting for local AI…" : req?.status === "running" ? "Local AI checking…" : "Re-check with local AI"}
          </button>
        )}
        {req?.status === "done" && <span className="text-xs text-violet-700 dark:text-violet-300">Local AI re-check done (report v{req.report_version}{req.agents ? ", agents" : ", fallback to DAG"})</span>}
        <a className="btn2" href={`/api/applications/${id}/report.pdf`} target="_blank">Download report</a>
        <a className="btn2" href={`/api/applications/${id}/report.html?view=institution`} target="_blank">What the college sees</a>
      </div>

      {/* Verdict */}
      <div data-tour="status" className={`rounded-2xl p-5 flex flex-wrap items-center gap-5 ${nHigh ? "bg-red-600 text-white" : nMed ? "bg-amber-400 text-amber-950" : "bg-emerald-600 text-white"}`}>
        <Status size={52} strokeWidth={1.6} />
        <div className="flex-1 min-w-[240px]">
          <div className="text-2xl font-bold">
            {nHigh ? `${nHigh} serious problem${nHigh > 1 ? "s" : ""} found` : nMed ? `${nMed} thing${nMed > 1 ? "s" : ""} to check` : "All checks passed"}
          </div>
          <div className="opacity-90">
            {flags.length ? `Go through them one by one below. You decide on each. ${reviewed} of ${flags.length} reviewed.`
              : `Every document is present, valid and consistent. ${a.verification?.verified} of ${a.verification?.total} confirmed with the issuing office.`}
          </div>
          {flags.length > 0 && <div className="mt-2 h-2 rounded bg-white/30 max-w-md"><div className="h-2 rounded bg-white" style={{ width: `${(reviewed / flags.length) * 100}%` }} /></div>}
        </div>
        {flags.length > 0 && <button className="px-5 py-3 rounded-xl bg-white text-slate-900 font-semibold shadow hover:shadow-lg inline-flex items-center gap-2"
          onClick={() => { setCheck(""); go(flags.findIndex((f: any) => f.status === "OPEN") >= 0 ? flags.findIndex((f: any) => f.status === "OPEN") : 0); document.getElementById("workspace")?.scrollIntoView({ behavior: "smooth" }); }}>
          {reviewed ? "Continue review" : "Start review"} <ChevronRight size={18} /></button>}
      </div>

      {/* The 9 checks */}
      <div data-tour="checks" className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2">
        {CHECKS.map((c) => {
          const fs = live.filter((f: any) => c.codes.includes(f.code));
          const bad = fs.some((f: any) => f.severity === "HIGH"), warn = !bad && fs.some((f: any) => f.severity === "MEDIUM");
          const Icon = CHECK_ICON[c.key];
          return (
            <button key={c.key} title={c.plain} onClick={() => { setCheck(check === c.key ? "" : c.key); setIdx(0); }}
              className={`rounded-xl p-3 text-left border transition hover:-translate-y-0.5 hover:shadow ${check === c.key ? "ring-2 ring-orange-400" : ""} ${bad ? "bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-900" : warn ? "bg-amber-50 border-amber-200 dark:bg-amber-950 dark:border-amber-900" : "bg-white border-slate-200 dark:bg-slate-900 dark:border-slate-800"}`}>
              <div className="flex items-center justify-between">
                <Icon size={20} className={bad ? "text-red-600" : warn ? "text-amber-600" : "text-slate-500"} />
                {fs.length ? <span className={`text-xs font-bold ${bad ? "text-red-600" : warn ? "text-amber-600" : "text-sky-600"}`}>{fs.length}</span> : <Check size={16} className="text-emerald-600" />}
              </div>
              <div className="text-xs font-medium leading-tight mt-2">{c.title}</div>
            </button>
          );
        })}
      </div>

      {/* Workspace */}
      <div id="workspace" className="grid gap-4 xl:grid-cols-[230px_minmax(0,1fr)_400px] scroll-mt-4">
        {/* Documents */}
        <div data-tour="docs" className="space-y-3">
          {[{ title: "", items: [FORM] }, ...groups].map((g) => g.items.length > 0 && (
            <div key={g.title || "form"}>
              {g.title && <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">{g.title}</div>}
              <div className="grid grid-cols-2 xl:grid-cols-1 gap-2">
                {g.items.map((x: any) => {
                  const key = x === FORM ? FORM : x.id;
                  const n = live.filter((f: any) => docOf(f) === key).length;
                  const sevHigh = live.some((f: any) => docOf(f) === key && f.severity === "HIGH");
                  return (
                    <button key={key} onClick={() => { setDocSel(key); const j = shown.findIndex((f: any) => docOf(f) === key); if (j >= 0) go(j); }}
                      className={`flex items-center gap-2 p-2 rounded-xl border text-left transition ${docSel === key ? "border-slate-900 dark:border-white bg-white dark:bg-slate-800 shadow" : "border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-900 hover:bg-white"}`}>
                      <div className="w-10 h-12 shrink-0 rounded bg-slate-100 dark:bg-slate-700 overflow-hidden grid place-items-center">
                        {x === FORM ? <Building2 size={18} className="text-slate-500" /> : x.pages?.[0] ? <img src={`/api/blobs/${x.pages[0]}`} className="w-full h-full object-cover" alt="" /> : <FileText size={18} />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="text-xs font-medium leading-tight line-clamp-2">{x === FORM ? "Application form" : x.slot === "INFRA_PHOTOS" ? (x.facility || "Photo").replace(/_/g, " ").toLowerCase() : label(x)}</div>
                        <div className="text-[11px] text-slate-500 truncate">{x === FORM ? "claims and records" : x.filename}</div>
                      </div>
                      {n > 0 ? <span className={`text-[11px] font-bold text-white rounded-full px-1.5 ${sevHigh ? "bg-red-500" : "bg-amber-500"}`}>{n}</span> : <Check size={14} className="text-emerald-600" />}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
          {missing.map((s: string) => (
            <div key={s} className="flex items-center gap-2 p-2 rounded-xl border-2 border-dashed border-red-300 text-red-600">
              <FileWarning size={18} /><div className="text-xs font-medium">{d.taxonomy[s]}<div className="font-normal">not uploaded</div></div>
            </div>
          ))}
        </div>

        {/* Viewer */}
        <div data-tour="viewer" className="card p-3 min-w-0">
          {docSel === FORM || !doc ? (
            <div>
              <div className="font-semibold mb-2">Application form vs AICTE records</div>
              <table className="w-full text-sm"><thead><tr><th></th><th>College says</th><th>AICTE records</th><th>Documents say</th></tr></thead><tbody>
                {(rep.records_diff || []).map((r: any) => (
                  <tr key={r.item} className={`border-t border-slate-100 dark:border-slate-800 ${r.mismatch ? "bg-red-50 dark:bg-red-950" : ""}`}>
                    <td className="font-medium">{r.item}</td><td>{String(r.application ?? "–")}</td><td>{String(r.records ?? "–")}</td><td>{String(r.document ?? "–")}</td>
                  </tr>))}
              </tbody></table>
              {(a.form.facilities || []).length > 0 && <div className="mt-3 text-sm"><div className="font-semibold mb-1">Facilities claimed</div>
                {a.form.facilities.map((f: any) => <div key={f.id}>{f.id.replace(/_/g, " ").toLowerCase()}: {f.claimed_workstations} computers{f.claimed_area_sqm ? `, ${f.claimed_area_sqm} m²` : ""}</div>)}</div>}
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <div className="font-semibold">{label(doc)}</div>
                <span className="text-xs text-slate-500">{doc.filename}</span>
                {doc.scanned && <Chip text="scanned / handwritten" cls="bg-violet-100 text-violet-800" />}
                <div className="flex-1" />
                {heatmap && <label className="text-xs flex items-center gap-1"><input type="checkbox" checked={heat} onChange={(e) => setHeat(e.target.checked)} /> Show edit heatmap</label>}
              </div>
              <div className={`grid gap-3 ${dup && docOf(cur) === doc.id ? "md:grid-cols-2" : ""}`}>
                <div className="relative rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700 bg-white">
                  {doc.pages?.[0] && <img src={`/api/blobs/${doc.pages[0]}`} className="w-full block" alt={label(doc)} />}
                  {heatmap && heat && <img src={`/api/blobs/${heatmap}`} className="absolute inset-0 w-full h-full opacity-60" alt="" />}
                  {pinFlags.map((f: any) => {
                    const b = boxOf(f, doc);
                    if (!b) return null;
                    const n = shown.indexOf(f) + 1, on = f.id === cur?.id;
                    return (
                      <button key={f.id} onClick={() => go(shown.indexOf(f))} title={headline(f, label(doc))} className="absolute"
                        style={{ left: `${b[0] * 100}%`, top: `${b[1] * 100}%`, width: `${Math.max(b[2] * 100, 2)}%`, height: `${Math.max(b[3] * 100, 1.5)}%` }}>
                        <span className={`absolute inset-0 rounded border-2 ${on ? "border-red-500 bg-red-500/15 animate-pulse" : "border-red-400/70"}`} />
                        <span className={`absolute -left-3 -top-3 w-6 h-6 rounded-full grid place-items-center text-[11px] font-bold text-white shadow ${on ? "bg-red-600 scale-110" : "bg-red-400"}`}>{n}</span>
                      </button>
                    );
                  })}
                </div>
                {dup && docOf(cur) === doc.id && (
                  <div>
                    <div className="text-xs mb-1 font-semibold text-red-700">Same photo found in another college's application</div>
                    <img src={`/api/blobs/${dup.other_pages[0]}`} className="w-full rounded-lg border-2 border-red-300" alt="matching image" />
                    <div className="text-[11px] text-slate-500 mt-1">{dup.other_label} · {Math.round(dup.similarity * 100)}% similar</div>
                  </div>
                )}
              </div>
              {doc.qr && d.verifications.filter((v: any) => v.doc_id === doc.id && v.method === "qr").slice(0, 1).map((v: any) => (
                <div key={v.id} className="mt-3 text-xs">
                  <div className="font-semibold mb-1">QR code vs printed document</div>
                  <table className="w-full"><tbody>{Object.entries(v.details.claimed || {}).filter(([k]) => k !== "iss").map(([k, val]: any) => {
                    const dv = doc.fields?.[k]?.value;
                    return <tr key={k} className="border-t border-slate-100 dark:border-slate-800"><td className="text-slate-500">{k.replace(/_/g, " ")}</td><td>{String(val)}</td><td>{String(dv ?? "–")}</td>
                      <td>{dv == null ? "" : String(dv) === String(val) ? <Check size={14} className="text-emerald-600" /> : <X size={14} className="text-red-600" />}</td></tr>;
                  })}</tbody></table>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Problem stepper */}
        <div data-tour="problem" className="space-y-3 xl:sticky xl:top-4 self-start">
          {!cur ? (
            <div className="card p-6 text-center">
              <ShieldCheck size={40} className="mx-auto text-emerald-600" />
              <div className="font-semibold mt-2">Nothing to review here</div>
              <div className="text-sm text-slate-500">{check ? "No problems for this check." : "PRAMAAN found no problems in this application."}</div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <button className="btn2 px-2" onClick={() => go(idx - 1)} disabled={idx === 0} aria-label="Previous problem"><ChevronLeft size={18} /></button>
                <div className="flex-1 text-center text-sm"><b>Problem {Math.min(idx, shown.length - 1) + 1}</b> of {shown.length}{check && " (filtered)"}</div>
                <button className="btn2 px-2" onClick={() => go(idx + 1)} disabled={idx >= shown.length - 1} aria-label="Next problem"><ChevronRight size={18} /></button>
              </div>
              <div id={cur.id} className={`card p-4 border-2 ${SEV[cur.severity].ring}`}>
                <div className="flex items-center gap-2 text-xs font-semibold">
                  <span className={`w-2.5 h-2.5 rounded-full ${SEV[cur.severity].dot}`} />
                  <span className={SEV[cur.severity].text}>{SEV[cur.severity].word}</span>
                  <span className="text-slate-400">·</span><span className="text-slate-500">{CHECK_OF[cur.code] || cur.category}</span>
                  <span className="text-slate-400">·</span><span className="text-slate-500 truncate">{docLabelOf(cur)}</span>
                </div>
                <div className="text-lg font-semibold leading-snug mt-2">{headline(cur, docLabelOf(cur))}</div>
                {compare(cur) && (
                  <div className="grid grid-cols-2 gap-2 mt-3 text-sm">
                    <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950 p-2"><div className="text-[11px] text-slate-500">Should be</div><div className="font-medium break-words">{compare(cur)![0]}</div></div>
                    <div className="rounded-lg bg-red-50 dark:bg-red-950 p-2"><div className="text-[11px] text-slate-500">Found</div><div className="font-medium break-words">{compare(cur)![1]}</div></div>
                  </div>
                )}
                <div className="text-sm mt-3"><span className="text-slate-500">Next step: </span>{nextStep(cur)}</div>

                {cur.status !== "OPEN" ? (
                  <div className="mt-3 rounded-lg bg-slate-50 dark:bg-slate-800 p-2 text-sm flex items-start gap-2">
                    {cur.status === "DISMISSED" ? <X size={16} className="mt-0.5" /> : <Flag size={16} className="mt-0.5 text-red-600" />}
                    <div className="flex-1"><b>{cur.status === "DISMISSED" ? "Marked not a problem" : cur.status === "ESCALATED" ? "Escalated" : "Confirmed as a problem"}</b> by {cur.disposition?.by}<div className="text-slate-500">“{cur.disposition?.reason}”</div></div>
                    {idx < shown.length - 1 && <button className="btn shrink-0 inline-flex items-center gap-1" onClick={() => go(idx + 1)}>Next problem <ChevronRight size={16} /></button>}
                  </div>
                ) : can("dispose_flags") ? (
                  act ? (
                    <div className="mt-3 space-y-2">
                      <input autoFocus className="inp w-full" placeholder={act === "DISMISS" ? "Why is it not a problem? (required)" : "Why? (required, saved in the audit trail)"} value={reason} onChange={(e) => setReason(e.target.value)} />
                      <div className="flex gap-2">
                        <button className="btn flex-1" disabled={reason.trim().length < 3} onClick={() => dispose(act)}>Save</button>
                        <button className="btn2" onClick={() => setAct(null)}>Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <button className="px-3 py-2 rounded-lg bg-red-600 text-white font-medium hover:bg-red-700 inline-flex items-center justify-center gap-1" onClick={() => setAct("CONFIRM")}><Flag size={16} /> It's a problem</button>
                      <button className="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 font-medium hover:bg-slate-50 dark:hover:bg-slate-800 inline-flex items-center justify-center gap-1" onClick={() => setAct("DISMISS")}><X size={16} /> Not a problem</button>
                      <button className="col-span-2 text-xs text-slate-500 hover:underline" onClick={() => setAct("ESCALATE")}>Not sure, escalate to a senior officer</button>
                    </div>
                  )
                ) : <div className="text-xs text-slate-500 mt-3">Your role can view but not review findings.</div>}

                <button className="mt-3 text-xs text-slate-500 inline-flex items-center gap-1" onClick={() => setTech(!tech)}>
                  <ChevronDown size={14} className={tech ? "rotate-180" : ""} /> Technical details
                </button>
                {tech && (
                  <div className="mt-2 text-xs space-y-1 text-slate-600 dark:text-slate-300">
                    <div><b>Engine says:</b> {cur.title}. {cur.reason}</div>
                    <div>Detector: {cur.detector} v{cur.detector_version} · confidence {cur.confidence}</div>
                    <div>Finding {cur.id} · code {cur.code}</div>
                    {cur.evidence.filter((e: any) => e.type === "rule").map((e: any, i: number) => <div key={i}>Rule {e.rule_id} ({e.source_ref}) in {e.pack}</div>)}
                    {cur.evidence.filter((e: any) => e.type === "verification").map((e: any, i: number) => <div key={i}>Issuer: {e.source} → {VWORD[e.status] || e.status}</div>)}
                    <div className="italic">{cur.advisory_note}</div>
                  </div>
                )}
              </div>

              <div className="card p-2">
                <div className="text-xs font-semibold text-slate-500 px-1 pb-1">All problems</div>
                <div className="max-h-64 overflow-y-auto">
                  {shown.map((f: any, i: number) => (
                    <button key={f.id} onClick={() => go(i)} className={`w-full text-left flex items-start gap-2 px-2 py-1.5 rounded-lg text-xs ${f.id === cur.id ? "bg-slate-100 dark:bg-slate-800" : "hover:bg-slate-50 dark:hover:bg-slate-800/50"}`}>
                      <span className="w-5 shrink-0 text-slate-400">{i + 1}</span>
                      <span className={`w-2 h-2 rounded-full mt-1 shrink-0 ${SEV[f.severity].dot}`} />
                      <span className={`flex-1 ${f.status === "DISMISSED" ? "line-through text-slate-400" : ""}`}>{headline(f, docLabelOf(f))}</span>
                      {f.status !== "OPEN" && <Check size={14} className="text-emerald-600 shrink-0" />}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* More detail, folded away */}
      <div className="card">
        <div className="flex flex-wrap gap-1 p-2">
          <span className="text-sm font-semibold px-2 py-1.5">More details:</span>
          {[["issuer", "Issuer confirmations"], ["records", "AICTE records comparison"], ["institution", "What the college sees"], ["timeline", "How it was processed"], ["notes", "Officer notes"]].map(([k, l]) => (
            <button key={k} onClick={() => setMore(more === k ? "" : k)} className={`px-3 py-1.5 rounded-md text-sm ${more === k ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`}>{l}</button>
          ))}
        </div>
        {more && <div className="p-3 border-t border-slate-100 dark:border-slate-800 overflow-x-auto">
          {more === "issuer" && (
            <>
              <p className="text-sm text-slate-500 mb-2">PRAMAAN asked each issuing office (mock) whether the document is genuine, by scanning its signed QR code, checking its digital signature or looking up its reference number.</p>
              <table className="w-full text-sm"><thead><tr><th>Document</th><th>How</th><th>Issuing office</th><th>Answer</th></tr></thead><tbody>
                {d.verifications.map((v: any) => (
                  <tr key={v.id} className="border-t border-slate-100 dark:border-slate-800"><td>{label(docById(v.doc_id))}</td>
                    <td>{v.method === "qr" ? "Signed QR code" : v.method === "pdf_sig" ? "Digital signature" : "Reference lookup"}</td><td className="text-xs">{v.source || "–"}</td>
                    <td><Chip text={VWORD[v.status] || v.status} cls={VSTAT[v.status]} /></td></tr>))}
              </tbody></table>
              {can("dispose_flags") && <button className="btn2 mt-2" onClick={async () => { await api(`/applications/${id}/rerun`, { method: "POST" }); load(); }}>Ask the issuers again</button>}
            </>
          )}
          {more === "records" && (
            <table className="w-full text-sm"><thead><tr><th>Item</th><th>College says</th><th>AICTE records (mock)</th><th>Documents say</th></tr></thead><tbody>
              {(rep.records_diff || []).map((r: any) => <tr key={r.item} className={`border-t border-slate-100 dark:border-slate-800 ${r.mismatch ? "bg-red-50 dark:bg-red-950" : ""}`}><td>{r.item}</td><td>{String(r.application ?? "–")}</td><td>{String(r.records ?? "–")}</td><td>{String(r.document ?? "–")}</td></tr>)}
            </tbody></table>
          )}
          {more === "institution" && (
            <div className="text-sm space-y-1">
              <p className="text-slate-500 mb-2">The college only sees what it can fix. Signs of editing and other forensic details are never shown to them.</p>
              {d.institution_view.items.length === 0 && <div>Nothing to fix.</div>}
              {d.institution_view.items.map((i: any) => <div key={i.id}>• <b>{i.title}</b> – {i.action}</div>)}
              {d.institution_view.pending_authority_verification > 0 && <div>• Some documents need verification by the authority.</div>}
            </div>
          )}
          {more === "timeline" && <Timeline id={id!} reports={d.reports} />}
          {more === "notes" && (
            <div className="text-sm">
              {(a.observations || []).length === 0 && <div className="text-slate-500">No notes yet.</div>}
              {(a.observations || []).map((o: any, i: number) => <div key={i}><b>{o.by}</b>: {o.text}</div>)}
              {can("dispose_flags") && <div className="flex gap-2 mt-2"><input className="inp flex-1" value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Add a note for the file" />
                <button className="btn2" disabled={!obs} onClick={async () => { await api(`/applications/${id}/observations`, { json: { text: obs } }); setObs(""); load(); }}>Add</button></div>}
            </div>
          )}
        </div>}
      </div>

      {/* Decision bar */}
      <div data-tour="decision" className="fixed bottom-0 left-0 md:left-56 right-0 z-20 bg-white/95 dark:bg-slate-900/95 backdrop-blur border-t border-slate-200 dark:border-slate-800 px-4 py-3">
        <div className="max-w-[1500px] flex flex-wrap items-center gap-3">
          {a.decision ? (
            <div className="text-sm flex items-center gap-2"><Check className="text-emerald-600" size={18} /> <b>Decision recorded</b> by {a.decision.by}: {a.decision.text}</div>
          ) : highOpen.length > 0 ? (
            <>
              <Lock size={18} className="text-slate-500" />
              <div className="text-sm flex-1 min-w-[200px]"><b>Decision locked.</b> Review the {highOpen.length} remaining serious problem{highOpen.length > 1 ? "s" : ""} first.</div>
              <button className="btn" disabled>Record decision note</button>
            </>
          ) : !can("decision_note") ? (
            <div className="text-sm text-slate-500">All serious problems reviewed. A Senior Officer can now record the decision.</div>
          ) : (
            <>
              <input className="inp flex-1 min-w-[240px]" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Issue deficiency letter for the confirmed problems" />
              <button className="btn" disabled={!note} onClick={decide}>Record decision note</button>
            </>
          )}
          {msg && <div className="text-xs w-full">{msg}</div>}
        </div>
      </div>
    </div>
  );
}

function Timeline({ id, reports }: { id: string; reports: any[] }) {
  const [t, setT] = useState<any>(null);
  useEffect(() => { api(`/applications/${id}/timeline`).then(setT); }, [id, reports.length]);
  if (!t) return <div className="text-xs text-slate-500">Loading timeline…</div>;
  const u = t.usage;
  return (
    <div data-testid="agent-timeline" className="text-sm space-y-1">
      <div className="mb-2">
        Report versions: {reports.map((r: any) => `v${r.version}${r.changed ? " (after re-upload)" : ""}`).join(" → ")}. Checked in {((t.elapsed_ms || 0) / 1000).toFixed(1)} s,{" "}
        {t.agents ? "with agents" : "fixed pipeline (no agents)"}{u && `: ${u.llm_calls} model calls, ${u.tokens_in + u.tokens_out} tokens, ${u.model}`}.
      </div>
      {t.lines.map((l: any, i: number) => (
        <div key={i} className={`flex gap-2 ${l.kind === "fallback" ? "text-amber-700 dark:text-amber-400" : l.kind === "error" ? "text-red-600" : ""}`}>
          <span className="w-4 shrink-0">{l.kind === "agent" ? "•" : l.kind === "fallback" ? "↺" : l.kind === "error" ? "!" : "·"}</span>
          <span className={l.kind === "doc" ? "text-slate-500" : ""}>{l.text}</span>
        </div>
      ))}
    </div>
  );
}
