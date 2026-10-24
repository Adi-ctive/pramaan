import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Chip, VSTAT } from "../api";
import { useUser } from "../ctx";
import { CATEGORY, CHECKS, CHECK_OF, SEVERITY_WORD } from "../labels";

type Box = { bbox: number[]; color: string; label: string; dashed?: boolean };
const ORDER = ["HIGH", "MEDIUM", "LOW", "INFO"];
const SEVCLS: Record<string, string> = {
  HIGH: "bg-red-600 text-white", MEDIUM: "bg-amber-400 text-amber-950", LOW: "bg-sky-100 text-sky-800", INFO: "bg-slate-100 text-slate-700",
};
const VWORD: Record<string, string> = {
  VERIFIED: "Confirmed", MISMATCH: "Does not match", SIGNATURE_INVALID: "Signature invalid", NOT_FOUND: "Not found at issuer",
  SOURCE_UNAVAILABLE: "Issuer did not respond", MANUAL_REVIEW: "Needs manual check", EXPIRED: "Expired",
};

function Viewer({ doc, page, boxes, heatmap, pulse, compare }: { doc: any; page: number; boxes: Box[]; heatmap?: string; pulse?: number[]; compare?: { pages: string[]; label: string } }) {
  const [hm, setHm] = useState(true);
  if (!doc) return <div className="card p-6 text-sm text-slate-500">Pick a document to view it.</div>;
  const src = doc.pages[page] ? `/api/blobs/${doc.pages[page]}` : "";
  return (
    <div>
      {heatmap && (
        <label className="flex items-center gap-2 text-xs mb-2 text-slate-600 dark:text-slate-300">
          <input type="checkbox" checked={hm} onChange={(e) => setHm(e.target.checked)} /> Show edit heatmap (warm colours = noise pattern differs from the rest of the page)
        </label>
      )}
      <div className={`grid gap-3 ${compare ? "md:grid-cols-2" : ""}`}>
        <div className="relative rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700 bg-white">
          {src && <img src={src} className="w-full block" alt="document page" />}
          {heatmap && hm && <img src={`/api/blobs/${heatmap}`} className="absolute inset-0 w-full h-full" style={{ opacity: 0.6 }} alt="heatmap" />}
          {boxes.map((b, i) => (
            <div key={i} title={b.label} className="absolute group"
              style={{ left: `${b.bbox[0] * 100}%`, top: `${b.bbox[1] * 100}%`, width: `${Math.max(b.bbox[2] * 100, 1)}%`, height: `${Math.max(b.bbox[3] * 100, 1)}%`, border: `2px ${b.dashed ? "dashed" : "solid"} ${b.color}` }}>
              <span className="hidden group-hover:block absolute -top-5 left-0 text-[10px] bg-black text-white px-1 whitespace-nowrap z-10">{b.label}</span>
            </div>
          ))}
          {pulse && <div className="absolute animate-pulse" style={{ left: `${pulse[0] * 100 - 0.5}%`, top: `${pulse[1] * 100 - 0.5}%`, width: `${pulse[2] * 100 + 1}%`, height: `${pulse[3] * 100 + 1}%`, border: "3px solid #f43f5e", background: "rgba(244,63,94,.15)" }} />}
        </div>
        {compare && (
          <div>
            <div className="text-xs mb-1 font-medium text-red-700">Same photo found in another college's application: {compare.label}</div>
            <img src={`/api/blobs/${compare.pages[0]}`} className="w-full rounded-lg border border-red-300" alt="matching document" />
          </div>
        )}
      </div>
    </div>
  );
}

function evidenceLabel(e: any, docs: any[]) {
  const d = docs.find((x) => x.id === e.document_id);
  if (e.type === "field") return `${e.key?.replace(/_/g, " ")}: ${e.value ?? "-"}${d ? ` (${d.filename})` : ""}`;
  if (e.type === "region" || e.type === "heatmap") return `Show on ${d?.filename || "document"}`;
  if (e.type === "duplicate") return `Compare with matching image (similarity ${e.similarity})`;
  if (e.type === "verification") return `Issuer response: ${VWORD[e.status] || e.status}`;
  if (e.type === "record") return `AICTE record: ${e.key} = ${JSON.stringify(e.value)}`;
  if (e.type === "metadata") return `${e.key?.replace(/_/g, " ")}: ${JSON.stringify(e.value).slice(0, 50)}`;
  if (e.type === "rule") return `Rule ${e.rule_id}`;
  return e.type;
}

function Finding({ f, docs, onEvidence, onDone, canDispose }: { f: any; docs: any[]; onEvidence: (e: any) => void; onDone: () => void; canDispose: boolean }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const act = async (action: string) => {
    try { await api(`/flags/${f.id}/dispose`, { json: { action, reason } }); setReason(""); setOpen(false); onDone(); } catch (e: any) { setErr(e.message); }
  };
  const done = f.status !== "OPEN";
  return (
    <div id={f.id} className={`card p-4 ${f.status === "DISMISSED" ? "opacity-50" : ""}`}>
      <div className="flex items-start gap-3">
        <span className={`shrink-0 text-[11px] font-bold px-2 py-0.5 rounded-full ${SEVCLS[f.severity]}`}>{SEVERITY_WORD[f.severity]}</span>
        <div className="flex-1 min-w-0">
          <div className="font-semibold leading-snug">{f.title}</div>
          <div className="text-sm text-slate-600 dark:text-slate-300 mt-1">{f.reason}</div>
          {(f.expected != null || f.observed != null) && (
            <div className="mt-2 inline-grid grid-cols-[auto_1fr] gap-x-3 text-xs rounded bg-slate-50 dark:bg-slate-800 px-2 py-1">
              <span className="text-slate-500">Expected</span><span>{String(f.expected ?? "-")}</span>
              <span className="text-slate-500">Found</span><span className="font-medium">{String(f.observed ?? "-")}</span>
            </div>
          )}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {f.evidence.filter((e: any) => e.type !== "rule").map((e: any, i: number) => (
              <button key={i} className="text-xs px-2 py-1 rounded-md bg-orange-50 text-orange-800 hover:bg-orange-100 dark:bg-orange-950 dark:text-orange-200" onClick={() => onEvidence(e)}>
                {evidenceLabel(e, docs)}
              </button>
            ))}
          </div>
          {f.recommended_action && <div className="text-xs mt-2"><span className="text-slate-500">Suggested next step:</span> {f.recommended_action}</div>}
          {f.disposition && <div className="text-xs mt-2 text-emerald-700 dark:text-emerald-400">{f.disposition.action.toLowerCase()}ed by {f.disposition.by}: "{f.disposition.reason}"</div>}
          <div className="text-[11px] text-slate-400 mt-2">Check: {CHECK_OF[f.code] || f.category} · {f.detector} · confidence {f.confidence} · {f.id}</div>
        </div>
        {canDispose && !done && !open && <button className="btn2 shrink-0" onClick={() => setOpen(true)}>Review</button>}
        {done && <Chip text={f.status.toLowerCase()} cls="bg-slate-100 text-slate-600" />}
      </div>
      {open && (
        <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 flex flex-wrap gap-2 items-center">
          <input autoFocus className="inp flex-1 min-w-[180px]" placeholder="Why? (required, saved in the audit trail)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <button className="btn" disabled={reason.length < 3} onClick={() => act("CONFIRM")}>Confirm problem</button>
          <button className="btn2" disabled={reason.length < 3} onClick={() => act("DISMISS")}>Dismiss</button>
          <button className="btn2" disabled={reason.length < 3} onClick={() => act("ESCALATE")}>Escalate</button>
          <button className="text-xs text-slate-500" onClick={() => setOpen(false)}>Cancel</button>
          {err && <div className="text-xs text-red-600 w-full">{err}</div>}
        </div>
      )}
    </div>
  );
}

export default function Detail() {
  const { id } = useParams();
  const user = useUser()!;
  const [d, setD] = useState<any>(null);
  const [sel, setSel] = useState("");
  const [page, setPage] = useState(0);
  const [check, setCheck] = useState("");
  const [tab, setTab] = useState("issuer");
  const [pulse, setPulse] = useState<number[] | undefined>();
  const [compare, setCompare] = useState<any>();
  const [obs, setObs] = useState("");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => api(`/applications/${id}`).then((x) => { setD(x); setSel((s) => s || x.documents.find((k: any) => !k.superseded)?.id || ""); });
  useEffect(() => { load(); }, [id]);
  const flags = useMemo(() => (d?.flags || []).slice().sort((a: any, b: any) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity)), [d]);
  if (!d) return <div className="text-sm text-slate-500">Loading application…</div>;
  const a = d.application, rep = d.report || {};
  const can = (c: string) => user.caps.includes(c);
  const live = flags.filter((f: any) => f.status !== "DISMISSED");
  const nHigh = live.filter((f: any) => f.severity === "HIGH").length, nMed = live.filter((f: any) => f.severity === "MEDIUM").length;
  const shown = check ? flags.filter((f: any) => CHECKS.find((c) => c.key === check)!.codes.includes(f.code)) : flags;
  const docs = d.documents;
  const current = docs.filter((x: any) => !x.superseded);
  const doc = docs.find((x: any) => x.id === sel);
  const boxes: Box[] = [];
  let heatmap: string | undefined;
  if (doc) {
    Object.entries(doc.fields || {}).forEach(([k, v]: any) => v.bbox && v.page === page && boxes.push({ bbox: v.bbox, color: "#2563eb", label: `${k.replace(/_/g, " ")}: ${v.value}` }));
    if (doc.qr && doc.qr.page === page) boxes.push({ bbox: doc.qr.bbox, color: "#16a34a", label: "Signed QR code" });
    live.filter((f: any) => f.doc_id === doc.id).forEach((f: any) => f.evidence.forEach((e: any) => e.type === "region" && e.bbox && e.bbox[2] < 1 && boxes.push({ bbox: e.bbox, color: "#dc2626", label: f.title })));
    heatmap = doc.images?.find((i: any) => i.heatmap)?.heatmap;
  }
  const onEvidence = (e: any) => {
    setCompare(undefined);
    if (e.document_id && docs.some((x: any) => x.id === e.document_id)) { setSel(e.document_id); setPage(e.page || 0); }
    setPulse(e.bbox && e.bbox[2] < 1 ? e.bbox : undefined);
    if (e.type === "duplicate" && e.other_pages?.length) setCompare({ pages: e.other_pages, label: e.other_label });
    if (e.type === "verification") setTab("issuer");
    if (e.type === "record") setTab("records");
    document.getElementById("viewer")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const highOpen = flags.filter((f: any) => f.severity === "HIGH" && f.status === "OPEN");
  const photos = current.filter((x: any) => x.slot === "INFRA_PHOTOS");
  const facilities = a.form.facilities || [];
  const missing = d.required_slots.filter((s: string) => !current.some((x: any) => x.slot === s));
  const decide = async () => {
    try { await api(`/applications/${id}/decision`, { json: { text: note } }); setMsg("Decision note recorded."); load(); }
    catch (e: any) { setMsg(e.status === 409 ? `Still blocked: ${e.body.open_high.length} serious finding(s) not reviewed.` : e.message); }
  };
  return (
    <div className="space-y-5">
      <div>
        <Link to="/" className="text-sm text-orange-600 hover:underline">← All applications</Link>
        <div className="flex flex-wrap items-end gap-3 mt-1">
          <h1 className="text-2xl font-bold tracking-tight">{a.form.institution_name}</h1>
          <span className="text-sm text-slate-500 pb-1">{CATEGORY[a.category] || a.category} · via {d.host} · {a.region} region · ref {a.external_ref}</span>
        </div>
      </div>

      {/* Verdict */}
      <div className={`rounded-2xl p-5 ${nHigh ? "bg-red-600 text-white" : nMed ? "bg-amber-400 text-amber-950" : "bg-emerald-600 text-white"}`}>
        <div className="text-xl font-bold">
          {nHigh ? `${nHigh} serious problem${nHigh > 1 ? "s" : ""} found${nMed ? `, ${nMed} more to check` : ""}` : nMed ? `${nMed} item${nMed > 1 ? "s" : ""} to check` : "All checks passed"}
        </div>
        <div className="text-sm opacity-90 mt-1">
          {nHigh ? "Review each serious finding below before recording a decision." : nMed ? "Nothing serious, but some items need a person to look." : `Every document is present, valid and consistent. ${a.verification?.verified} of ${a.verification?.total} confirmed with the issuing office.`}
          {" "}PRAMAAN only advises. The officer decides.
        </div>
      </div>

      {/* Checks grid */}
      <div>
        <div className="text-sm font-semibold mb-2">The 9 checks {check && <button className="ml-2 text-xs text-orange-600" onClick={() => setCheck("")}>show all findings</button>}</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-9 gap-2">
          {CHECKS.map((c) => {
            const fs = live.filter((f: any) => c.codes.includes(f.code));
            const sev = fs.some((f: any) => f.severity === "HIGH") ? "bad" : fs.some((f: any) => f.severity === "MEDIUM") ? "warn" : fs.length ? "minor" : "ok";
            return (
              <button key={c.key} title={c.plain} onClick={() => setCheck(check === c.key ? "" : c.key)}
                className={`rounded-xl p-3 text-left border transition ${check === c.key ? "ring-2 ring-orange-400" : ""} ${sev === "bad" ? "bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-900" : sev === "warn" ? "bg-amber-50 border-amber-200 dark:bg-amber-950 dark:border-amber-900" : "bg-white border-slate-200 dark:bg-slate-900 dark:border-slate-800"}`}>
                <div className={`text-lg font-bold ${sev === "bad" ? "text-red-600" : sev === "warn" ? "text-amber-600" : sev === "minor" ? "text-sky-600" : "text-emerald-600"}`}>{sev === "ok" ? "✓" : `✗ ${fs.length}`}</div>
                <div className="text-xs font-medium leading-tight">{c.title}</div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        {/* Findings */}
        <div className="space-y-3">
          <div className="text-sm font-semibold">{check ? CHECKS.find((c) => c.key === check)!.title : "What was found"} ({shown.length})</div>
          {shown.length ? shown.map((f: any) => <Finding key={f.id} f={f} docs={docs} onEvidence={onEvidence} onDone={load} canDispose={can("dispose_flags")} />)
            : <div className="card p-4 text-sm text-slate-500">Nothing found here.</div>}
        </div>
        {/* Document viewer */}
        <div id="viewer" className="xl:sticky xl:top-4 self-start space-y-2">
          <div className="text-sm font-semibold">Documents ({current.length} uploaded{missing.length ? `, ${missing.length} missing` : ""})</div>
          <div className="flex flex-wrap gap-1.5">
            {current.map((x: any) => {
              const n = live.filter((f: any) => f.doc_id === x.id).length;
              return (
                <button key={x.id} onClick={() => { setSel(x.id); setPage(0); setPulse(undefined); setCompare(undefined); }}
                  className={`text-xs px-2 py-1 rounded-md border ${x.id === sel ? "bg-slate-900 text-white border-slate-900 dark:bg-white dark:text-slate-900" : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700"}`}>
                  {d.taxonomy[x.slot] || x.slot}{x.slot === "INFRA_PHOTOS" ? ` (${x.facility})` : ""}{n > 0 && <span className="ml-1 text-red-500">●</span>}
                </button>
              );
            })}
            {missing.map((s: string) => <span key={s} className="text-xs px-2 py-1 rounded-md border border-dashed border-red-300 text-red-600">{d.taxonomy[s]} - missing</span>)}
          </div>
          {doc?.scanned && <div className="text-xs rounded bg-violet-50 text-violet-800 dark:bg-violet-950 dark:text-violet-200 px-2 py-1">Scanned or handwritten. The machine could not read it reliably, so an officer must read it.</div>}
          <div className="card p-3"><Viewer doc={doc} page={page} boxes={boxes} heatmap={heatmap} pulse={pulse} compare={compare} /></div>
          <div className="text-[11px] text-slate-500"><span className="text-blue-600">Blue boxes</span> are values read from the document. <span className="text-green-600">Green</span> is the signed QR code. <span className="text-red-600">Red</span> marks a problem area.</div>
        </div>
      </div>

      {photos.length > 0 && (
        <div>
          <div className="text-sm font-semibold mb-2">Lab and campus photos</div>
          <div className="grid md:grid-cols-2 gap-3">
            {facilities.map((fac: any) => {
              const ph = photos.filter((p: any) => p.facility === fac.id);
              const counted = ph.reduce((n: number, p: any) => n + (p.images?.[0]?.count?.count || 0), 0);
              const fl = live.filter((f: any) => ["INFRASTRUCTURE"].includes(f.category) || f.code.startsWith("DUPLICATE")).filter((f: any) => f.title.includes(fac.id) || ph.some((p: any) => p.id === f.doc_id));
              return (
                <div key={fac.id} className="card p-3 flex gap-3">
                  <div className="flex gap-1">{ph.map((p: any) => <img key={p.id} onClick={() => { setSel(p.id); document.getElementById("viewer")?.scrollIntoView({ behavior: "smooth" }); }} src={`/api/blobs/${p.pages[0]}`} className="w-24 h-18 object-cover rounded cursor-pointer" alt={p.filename} />)}</div>
                  <div className="text-sm">
                    <div className="font-semibold">{fac.id.replace(/_/g, " ").toLowerCase()}</div>
                    <div className={counted < fac.claimed_workstations * 0.85 ? "text-red-600 font-medium" : ""}>{counted} computers seen in photos, {fac.claimed_workstations} claimed</div>
                    {fl.map((f: any) => <div key={f.id} className="text-xs text-red-600">• {f.title}</div>)}
                    {fl.length > 0 && <div className="text-xs mt-1 font-medium text-amber-700">Suggest: {fl.some((f: any) => f.code === "INFRA_SHORTFALL") ? "physical inspection" : "ask for more evidence"}</div>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* More detail */}
      <div className="card">
        <div className="flex flex-wrap gap-1 p-2 border-b border-slate-100 dark:border-slate-800">
          {[["issuer", "Issuer confirmations"], ["records", "AICTE records comparison"], ["institution", "What the college sees"], ["timeline", "How it was processed"]].map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-md text-sm ${tab === k ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`}>{l}</button>
          ))}
        </div>
        <div className="p-3 overflow-x-auto">
          {tab === "issuer" && (
            <>
              <p className="text-xs text-slate-500 mb-2">Each document is checked against the office that issued it, by scanning its signed QR code or looking up its reference number (mock issuers).</p>
              <table className="w-full text-sm"><thead><tr><th>Document</th><th>How</th><th>Issuing office</th><th>Result</th><th>When</th></tr></thead><tbody>
                {d.verifications.map((v: any) => (
                  <tr key={v.id} className="border-t border-slate-100 dark:border-slate-800"><td>{d.taxonomy[docs.find((x: any) => x.id === v.doc_id)?.slot] || "-"}</td><td>{v.method === "qr" ? "Signed QR code" : "Reference lookup"}</td><td className="text-xs">{v.source || "-"}</td>
                    <td><Chip text={VWORD[v.status] || v.status} cls={VSTAT[v.status]} /><div className="text-[11px] text-slate-500">{v.details.reason || (v.details.diffs || []).map((x: any) => `${x.field}: issuer says "${x.source}", document says "${x.document}"`).join("; ")}</div></td>
                    <td className="text-xs whitespace-nowrap">{v.ts.slice(0, 16).replace("T", " ")}</td></tr>
                ))}
              </tbody></table>
              {can("dispose_flags") && <button className="btn2 mt-2" onClick={async () => { await api(`/applications/${id}/rerun`, { method: "POST" }); load(); }}>Check again with issuers</button>}
            </>
          )}
          {tab === "records" && (
            <table className="w-full text-sm"><thead><tr><th>Item</th><th>College claims</th><th>AICTE records (mock)</th><th>Document says</th></tr></thead><tbody>
              {(rep.records_diff || []).map((r: any) => <tr key={r.item} className={`border-t border-slate-100 dark:border-slate-800 ${r.mismatch ? "bg-red-50 dark:bg-red-950" : ""}`}><td>{r.item}{r.mismatch && <span className="text-red-600 text-xs ml-1">mismatch</span>}</td><td>{String(r.application ?? "-")}</td><td>{String(r.records ?? "-")}</td><td>{String(r.document ?? "-")}</td></tr>)}
            </tbody></table>
          )}
          {tab === "institution" && (
            <div className="text-sm space-y-1">
              <p className="text-xs text-slate-500 mb-2">The college sees only what it can fix. Signs of editing and other forensic details are never shown to them.</p>
              {d.institution_view.items.length === 0 && <div>Nothing to fix.</div>}
              {d.institution_view.items.map((i: any) => <div key={i.id}>• <b>{i.title}</b> - {i.action}</div>)}
              {d.institution_view.pending_authority_verification > 0 && <div>• Some documents need verification by the authority.</div>}
            </div>
          )}
          {tab === "timeline" && (
            <div className="text-xs space-y-1">
              <div className="mb-2">Report versions: {d.reports.map((r: any) => `v${r.version}${r.changed ? " (after re-upload)" : ""}`).join(" → ")}. Checked in {rep.elapsed_ms} ms using rule pack {d.pack}.</div>
              {(rep.timeline || []).map((t: any, i: number) => (
                <div key={i} className="flex gap-2">
                  <span className={`w-16 shrink-0 ${t.status === "reused" ? "text-slate-400" : t.status === "error" ? "text-red-600" : "text-emerald-700"}`}>{t.status === "reused" ? "not rerun" : t.status}</span>
                  <span className="flex-1">{t.stage.replace("doc:", "document: ")}{t.substages && <span className="text-slate-400"> - {t.substages.map((s: any) => s.stage).join(", ")}</span>}{t.note && <span className="text-slate-400"> - {t.note}</span>}</span>
                  <span>{t.ms ?? ""} ms</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Decision */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="font-semibold mb-1">Officer notes</div>
          {(a.observations || []).length === 0 && <div className="text-xs text-slate-500">No notes yet.</div>}
          {(a.observations || []).map((o: any, i: number) => <div key={i} className="text-sm"><b>{o.by}</b>: {o.text}</div>)}
          {can("dispose_flags") && <div className="flex gap-2 mt-2"><input className="inp flex-1" value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Add a note" />
            <button className="btn2" disabled={!obs} onClick={async () => { await api(`/applications/${id}/observations`, { json: { text: obs } }); setObs(""); load(); }}>Add</button></div>}
        </div>
        <div className="card p-4">
          <div className="font-semibold mb-1">Decision note</div>
          {a.decision ? <div className="text-sm"><b>{a.decision.by}</b>: {a.decision.text}</div> : (
            <>
              {highOpen.length > 0 && <div className="text-sm text-red-600 mb-2">Locked. Review the {highOpen.length} serious finding{highOpen.length > 1 ? "s" : ""} first (confirm or dismiss each with a reason).</div>}
              {!can("decision_note") && <div className="text-xs text-slate-500 mb-2">Only a Senior Officer can record the decision.</div>}
              <textarea className="inp w-full" rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Issue deficiency letter for the items above" disabled={!can("decision_note") || highOpen.length > 0} />
              <button className="btn mt-2" disabled={!can("decision_note") || highOpen.length > 0 || !note} onClick={decide}>Record decision note</button>
            </>
          )}
          {msg && <div className="text-xs mt-1">{msg}</div>}
        </div>
      </div>
    </div>
  );
}
