import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Chip, SEV, VSTAT } from "../api";
import { useUser } from "../main";

type Box = { bbox: number[]; color: string; label: string; dashed?: boolean };

function Viewer({ doc, page, boxes, heatmap, pulse, compare }: { doc: any; page: number; boxes: Box[]; heatmap?: string; pulse?: number[]; compare?: { pages: string[]; label: string } }) {
  const [hm, setHm] = useState(true);
  const [op, setOp] = useState(0.6);
  if (!doc) return <div className="card p-6 text-sm text-slate-500">Select a document.</div>;
  const src = doc.pages[page] ? `/api/blobs/${doc.pages[page]}` : "";
  return (
    <div className="card p-3">
      <div className="flex flex-wrap items-center gap-2 mb-2 text-sm">
        <span className="font-semibold">{doc.filename}</span>
        <Chip text={doc.slot} />
        {doc.scanned && <Chip text="scanned / handwritten" cls="bg-violet-100 text-violet-800" />}
        {heatmap && (
          <label className="flex items-center gap-1 text-xs ml-auto">
            <input type="checkbox" checked={hm} onChange={(e) => setHm(e.target.checked)} /> Tamper heatmap
            <input type="range" min={0.1} max={1} step={0.1} value={op} onChange={(e) => setOp(+e.target.value)} />
          </label>
        )}
      </div>
      <div className={`grid gap-2 ${compare ? "md:grid-cols-2" : ""}`}>
        <div className="relative border dark:border-slate-700 bg-white">
          {src && <img src={src} className="w-full block" alt="document page" />}
          {heatmap && hm && <img src={`/api/blobs/${heatmap}`} className="absolute inset-0 w-full h-full" style={{ opacity: op }} alt="heatmap" />}
          {boxes.map((b, i) => (
            <div key={i} title={b.label} className="absolute group"
              style={{ left: `${b.bbox[0] * 100}%`, top: `${b.bbox[1] * 100}%`, width: `${Math.max(b.bbox[2] * 100, 1)}%`, height: `${Math.max(b.bbox[3] * 100, 1)}%`, border: `2px ${b.dashed ? "dashed" : "solid"} ${b.color}` }}>
              <span className="hidden group-hover:block absolute -top-5 left-0 text-[10px] bg-black text-white px-1 whitespace-nowrap z-10">{b.label}</span>
            </div>
          ))}
          {pulse && <div className="absolute animate-pulse" style={{ left: `${pulse[0] * 100 - 0.5}%`, top: `${pulse[1] * 100 - 0.5}%`, width: `${pulse[2] * 100 + 1}%`, height: `${pulse[3] * 100 + 1}%`, border: "3px solid #f43f5e", background: "rgba(244,63,94,.12)" }} />}
        </div>
        {compare && (
          <div>
            <div className="text-xs mb-1 text-slate-500">Compare: {compare.label}</div>
            <img src={`/api/blobs/${compare.pages[0]}`} className="w-full border dark:border-slate-700" alt="compared document" />
          </div>
        )}
      </div>
    </div>
  );
}

function FlagCard({ f, onEvidence, onDone, canDispose }: { f: any; onEvidence: (e: any) => void; onDone: () => void; canDispose: boolean }) {
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const act = async (action: string) => {
    try { await api(`/flags/${f.id}/dispose`, { json: { action, reason } }); setReason(""); onDone(); } catch (e: any) { setErr(e.message); }
  };
  return (
    <div id={f.id} className={`card p-3 text-sm ${f.status === "DISMISSED" ? "opacity-50" : ""}`}>
      <div className="flex items-start gap-2">
        <Chip text={f.severity} cls={SEV[f.severity]} />
        <div className="flex-1">
          <div className="font-semibold">{f.title}</div>
          <div className="text-[11px] text-slate-500">{f.id} · {f.code} · {f.category}</div>
        </div>
        <Chip text={f.status} />
      </div>
      <p className="mt-2">{f.reason}</p>
      {(f.expected != null || f.observed != null) && (
        <div className="mt-1 text-xs grid grid-cols-[70px_1fr] gap-x-2"><span className="text-slate-500">Expected</span><span>{String(f.expected ?? "-")}</span><span className="text-slate-500">Observed</span><span>{String(f.observed ?? "-")}</span></div>
      )}
      <div className="mt-2 flex flex-wrap gap-1">
        {f.evidence.map((e: any, i: number) => (
          <button key={i} className="text-[11px] px-1.5 py-0.5 rounded border border-slate-300 dark:border-slate-700 hover:bg-blue-50 dark:hover:bg-slate-800" onClick={() => onEvidence(e)}>
            {e.type}{e.key ? `: ${e.key}` : ""}{e.rule_id ? `: ${e.rule_id}` : ""}{e.value != null && e.type !== "rule" ? ` = ${JSON.stringify(e.value).slice(0, 40)}` : ""}{e.similarity ? ` (sim ${e.similarity})` : ""}
          </button>
        ))}
      </div>
      <div className="mt-2 text-[11px] text-slate-500">{f.detector} v{f.detector_version} · confidence {f.confidence} · {f.advisory_note}</div>
      {f.recommended_action && <div className="text-[11px] mt-1">Suggested action: {f.recommended_action}</div>}
      {f.disposition && <div className="text-[11px] mt-1 text-emerald-700">{f.disposition.action} by {f.disposition.by}: "{f.disposition.reason}"</div>}
      {canDispose && (
        <div className="mt-2 flex flex-wrap gap-1 items-center">
          <input className="inp flex-1 min-w-[120px]" placeholder="Reason (required)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <button className="btn2" disabled={reason.length < 3} onClick={() => act("CONFIRM")}>Confirm</button>
          <button className="btn2" disabled={reason.length < 3} onClick={() => act("DISMISS")}>Dismiss</button>
          <button className="btn2" disabled={reason.length < 3} onClick={() => act("ESCALATE")}>Escalate</button>
        </div>
      )}
      {err && <div className="text-xs text-red-600">{err}</div>}
    </div>
  );
}

export default function Detail() {
  const { id } = useParams();
  const user = useUser()!;
  const [d, setD] = useState<any>(null);
  const [sel, setSel] = useState<string>("");
  const [page, setPage] = useState(0);
  const [tab, setTab] = useState("Flags");
  const [pulse, setPulse] = useState<number[] | undefined>();
  const [compare, setCompare] = useState<any>();
  const [overlays, setOverlays] = useState<Record<string, boolean>>({ Fields: true, QR: true, Regions: true });
  const [obs, setObs] = useState("");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => api(`/applications/${id}`).then((x) => { setD(x); setSel((s) => s || x.documents.find((k: any) => !k.superseded)?.id || ""); });
  useEffect(() => { load(); }, [id]);
  const doc = d?.documents.find((x: any) => x.id === sel);
  const flags = useMemo(() => (d?.flags || []).slice().sort((a: any, b: any) => ["HIGH", "MEDIUM", "LOW", "INFO"].indexOf(a.severity) - ["HIGH", "MEDIUM", "LOW", "INFO"].indexOf(b.severity)), [d]);
  if (!d) return <div className="text-sm text-slate-500">Loading…</div>;
  const a = d.application, rep = d.report || {};
  const can = (c: string) => user.caps.includes(c);
  const docFlags = (docId: string) => flags.filter((f: any) => f.doc_id === docId && f.status !== "DISMISSED");
  const boxes: Box[] = [];
  let heatmap: string | undefined;
  if (doc) {
    if (overlays.Fields) Object.entries(doc.fields || {}).forEach(([k, v]: any) => v.bbox && v.page === page && boxes.push({ bbox: v.bbox, color: "#2563eb", label: `${k}: ${v.value} (${v.conf})` }));
    if (overlays.QR && doc.qr && doc.qr.page === page) boxes.push({ bbox: doc.qr.bbox, color: "#16a34a", label: "QR (signed payload)" });
    if (overlays.Regions) docFlags(doc.id).forEach((f: any) => f.evidence.forEach((e: any) => e.type === "region" && e.bbox && e.bbox[2] < 1 && boxes.push({ bbox: e.bbox, color: "#dc2626", label: f.title })));
    if (doc.scanned) boxes.push({ bbox: [0.05, 0.05, 0.9, 0.9], color: "#7c3aed", label: "Handwriting / scan - manual read", dashed: true });
    heatmap = doc.images?.find((i: any) => i.heatmap)?.heatmap;
  }
  const onEvidence = (e: any) => {
    setCompare(undefined);
    if (e.document_id && d.documents.some((x: any) => x.id === e.document_id)) { setSel(e.document_id); setPage(e.page || 0); }
    setPulse(e.bbox && e.bbox[2] < 1 ? e.bbox : undefined);
    if (e.type === "duplicate" && e.other_pages?.length) setCompare({ pages: e.other_pages, label: `${e.other_label} (similarity ${e.similarity})` });
    if (e.type === "verification") setTab("Verify");
    if (e.type === "record") setTab("Records diff");
  };
  const highOpen = flags.filter((f: any) => f.severity === "HIGH" && f.status === "OPEN");
  const slots: string[] = d.required_slots;
  const present = new Set(d.documents.filter((x: any) => !x.superseded).map((x: any) => x.slot));
  const photos = d.documents.filter((x: any) => x.slot === "INFRA_PHOTOS" && !x.superseded);
  const facilities = a.form.facilities || [];
  const decide = async () => {
    try { await api(`/applications/${id}/decision`, { json: { text: note } }); setMsg("Decision note recorded."); load(); }
    catch (e: any) { setMsg(e.status === 409 ? `Blocked: ${e.body.open_high.length} HIGH flag(s) still open.` : e.message); }
  };
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Link to="/" className="text-blue-700 hover:underline">← Queue</Link>
        <h1 className="text-lg font-bold">{a.form.institution_name}</h1>
        <Chip text={a.status} />{a.decision && <Chip text="decision recorded" cls="bg-emerald-100 text-emerald-800" />}
      </div>
      <div className="grid gap-3 lg:grid-cols-[250px_minmax(0,1fr)_380px]">
        {/* LEFT */}
        <div className="space-y-3">
          <div className="card p-3 text-sm space-y-1">
            <div className="flex items-center gap-2"><div className="h-2 flex-1 bg-slate-200 rounded"><div className="h-2 rounded bg-red-500" style={{ width: `${a.risk}%` }} /></div><b>{a.risk}</b></div>
            <div className="text-[11px] text-slate-500">Review priority, not a decision</div>
            <div>{a.category} · {d.host}</div>
            <div className="text-xs text-slate-500">{a.institution_id} · {a.region} · ref {a.external_ref}</div>
            <div className="text-xs">Rule pack <span className="font-mono">{d.pack}</span></div>
            <div className="text-xs">Report v{rep.version} · {rep.mode} · {rep.elapsed_ms} ms</div>
            <div className="text-xs">Verified {a.verification?.verified}/{a.verification?.total}</div>
          </div>
          <div className="card p-3 text-sm">
            <div className="font-semibold mb-1">Documents</div>
            {slots.map((s) => (
              <div key={s} className="mb-1">
                <div className={`text-xs ${present.has(s) ? "" : "text-red-600 font-semibold"}`}>{present.has(s) ? "✓" : "✗"} {d.taxonomy[s]}</div>
                {d.documents.filter((x: any) => x.slot === s).map((x: any) => (
                  <button key={x.id} onClick={() => { setSel(x.id); setPage(0); setPulse(undefined); setCompare(undefined); }}
                    className={`block w-full text-left pl-4 text-xs truncate ${x.id === sel ? "font-bold text-blue-800 dark:text-blue-300" : ""} ${x.superseded ? "line-through opacity-50" : ""}`}>
                    {x.filename} {docFlags(x.id).length > 0 && !x.superseded && <span className="text-red-600">●{docFlags(x.id).length}</span>}
                  </button>
                ))}
              </div>
            ))}
          </div>
          {photos.length > 0 && (
            <div className="card p-3 text-sm space-y-2">
              <div className="font-semibold">Infrastructure gallery</div>
              {facilities.map((fac: any) => {
                const ph = photos.filter((p: any) => p.facility === fac.id);
                const counted = ph.reduce((n: number, p: any) => n + (p.images?.[0]?.count?.count || 0), 0);
                const fl = flags.filter((f: any) => f.category === "INFRASTRUCTURE" && (f.title.includes(fac.id) || ph.some((p: any) => p.id === f.doc_id)));
                return (
                  <div key={fac.id} className="border rounded p-2 dark:border-slate-700">
                    <div className="font-medium text-xs">{fac.id}</div>
                    <div className="flex gap-1 my-1">{ph.map((p: any) => <img key={p.id} onClick={() => setSel(p.id)} src={`/api/blobs/${p.pages[0]}`} className="w-16 h-12 object-cover cursor-pointer border" alt={p.filename} />)}</div>
                    <div className="text-xs">Monitors: {counted} detected / {fac.claimed_workstations} claimed</div>
                    {ph.map((p: any) => p.exif && <div key={p.id} className="text-[11px] text-slate-500">{p.filename}: {p.exif.lat ? `${p.exif.lat}, ${p.exif.lon}` : "no GPS"} · {p.exif.taken_at}</div>)}
                    {fl.map((f: any) => <div key={f.id} className="text-[11px] text-red-700">⚠ {f.title}</div>)}
                    {fl.length > 0 && <Chip text={fl.some((f: any) => f.code === "INFRA_SHORTFALL") ? "Physical inspection" : "Additional evidence"} cls="bg-amber-100 text-amber-800" />}
                  </div>
                );
              })}
            </div>
          )}
        </div>
        {/* CENTER */}
        <div className="space-y-2 min-w-0">
          <div className="flex flex-wrap gap-2 text-xs">
            {Object.keys(overlays).map((k) => (
              <label key={k} className="flex items-center gap-1"><input type="checkbox" checked={overlays[k]} onChange={(e) => setOverlays({ ...overlays, [k]: e.target.checked })} />{k}</label>
            ))}
            {doc?.pages.length > 1 && doc.pages.map((_: any, i: number) => <button key={i} className="btn2" onClick={() => setPage(i)}>p{i + 1}</button>)}
          </div>
          {doc && flags.some((f: any) => f.doc_id === doc.id && f.code === "DUPLICATE_ACROSS_INSTITUTIONS") && (
            <div className="card p-2 text-sm bg-amber-50 dark:bg-amber-950 border-amber-300">
              Visually matches a document from another institution.{" "}
              <button className="underline" onClick={() => onEvidence(flags.find((f: any) => f.doc_id === doc.id && f.code === "DUPLICATE_ACROSS_INSTITUTIONS").evidence[0])}>Open compare view</button>
            </div>
          )}
          <Viewer doc={doc} page={page} boxes={boxes} heatmap={heatmap} pulse={pulse} compare={compare} />
          {doc?.qr && (
            <div className="card p-3 text-xs">
              <div className="font-semibold mb-1">QR payload vs document</div>
              {d.verifications.filter((v: any) => v.doc_id === doc.id && v.method === "qr").slice(0, 1).map((v: any) => (
                <table key={v.id} className="w-full"><tbody>
                  {Object.entries(v.details.claimed || {}).filter(([k]) => k !== "iss").map(([k, val]: any) => {
                    const dv = doc.fields[k]?.value;
                    return <tr key={k}><td className="text-slate-500">{k}</td><td>{String(val)}</td><td>{String(dv ?? "-")}</td><td>{dv == null ? "" : String(dv) === String(val) ? "✓" : <span className="text-red-600 font-bold">mismatch</span>}</td></tr>;
                  })}
                </tbody></table>
              ))}
            </div>
          )}
        </div>
        {/* RIGHT */}
        <div className="space-y-2">
          <div className="card p-3 text-sm">
            <div className="font-semibold mb-1">Case summary</div>
            {(rep.summary || []).map((s: any, i: number) => (
              <p key={i} className="mb-1">{s.text} {s.flags.slice(0, 6).map((fid: string) => <a key={fid} href={`#${fid}`} onClick={() => setTab("Flags")} className="text-[10px] font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded mr-0.5">[{fid}]</a>)}</p>
            ))}
            <div className="text-[11px] text-slate-500">Generated from flags; no independent claims.</div>
          </div>
          <div className="flex flex-wrap gap-1">
            {["Flags", "Verify", "Records diff", "Timeline", "Institution view"].map((t) => <button key={t} onClick={() => setTab(t)} className={`btn2 text-xs ${tab === t ? "bg-slate-200 dark:bg-slate-700" : ""}`}>{t}</button>)}
          </div>
          <div className="space-y-2 lg:max-h-[70vh] lg:overflow-y-auto pr-1">
            {tab === "Flags" && (flags.length ? flags.map((f: any) => <FlagCard key={f.id} f={f} onEvidence={onEvidence} onDone={load} canDispose={can("dispose_flags")} />) : <div className="card p-3 text-sm">No flags. All checks passed.</div>)}
            {tab === "Verify" && (
              <div className="card overflow-x-auto"><table className="w-full text-xs"><thead><tr><th>Document</th><th>Method</th><th>Source</th><th>Status</th><th>Time</th></tr></thead><tbody>
                {d.verifications.map((v: any) => (
                  <tr key={v.id} className="border-t dark:border-slate-800"><td>{d.documents.find((x: any) => x.id === v.doc_id)?.slot}</td><td>{v.method}</td><td>{v.source}</td>
                    <td><Chip text={v.status} cls={VSTAT[v.status]} /><div className="text-[10px] text-slate-500">{v.details.reason || (v.details.diffs || []).map((x: any) => x.field).join(", ")}</div></td>
                    <td className="whitespace-nowrap">{v.ts.slice(5, 19).replace("T", " ")}<div className="font-mono text-[10px]">{v.response_digest}</div></td></tr>
                ))}
              </tbody></table>
                {can("dispose_flags") && <button className="btn2 m-2" onClick={async () => { await api(`/applications/${id}/rerun`, { method: "POST" }); load(); }}>Re-verify all</button>}
              </div>
            )}
            {tab === "Records diff" && (
              <div className="card overflow-x-auto"><table className="w-full text-xs"><thead><tr><th>Item</th><th>Application</th><th>AICTE records (mock)</th><th>Document</th></tr></thead><tbody>
                {(rep.records_diff || []).map((r: any) => <tr key={r.item} className={`border-t dark:border-slate-800 ${r.mismatch ? "bg-red-50 dark:bg-red-950" : ""}`}><td>{r.item}</td><td>{String(r.application ?? "-")}</td><td>{String(r.records ?? "-")}</td><td>{String(r.document ?? "-")}</td></tr>)}
              </tbody></table></div>
            )}
            {tab === "Timeline" && (
              <div className="card p-3 text-xs space-y-1">
                <div className="mb-1">Report versions: {d.reports.map((r: any) => `v${r.version}${r.changed ? " (re-upload)" : ""}`).join(" → ")}</div>
                {(rep.timeline || []).map((t: any, i: number) => (
                  <div key={i}>
                    <div className="flex gap-2"><span className={`w-14 ${t.status === "reused" ? "text-slate-400" : t.status === "ran" || t.status === "ok" ? "text-emerald-700" : "text-amber-700"}`}>{t.status}</span><span className="flex-1">{t.stage}</span><span>{t.ms ?? ""} ms</span></div>
                    {t.substages && <div className="pl-16 text-[10px] text-slate-500">{t.substages.map((s: any) => `${s.stage} ${s.ms}ms${s.note ? ` (${s.note})` : ""}`).join(" · ")}</div>}
                    {t.note && <div className="pl-16 text-[10px] text-slate-500">{t.note}</div>}
                  </div>
                ))}
              </div>
            )}
            {tab === "Institution view" && (
              <div className="card p-3 text-sm space-y-1">
                <div className="text-xs text-slate-500">What the institution sees in the upload widget. Forensic details are never shown.</div>
                {d.institution_view.items.map((i: any) => <div key={i.id}>• {i.title} - <span className="text-slate-500">{i.action}</span></div>)}
                {d.institution_view.pending_authority_verification > 0 && <div>• Some documents need verification by the authority.</div>}
              </div>
            )}
          </div>
        </div>
      </div>
      {/* BOTTOM BAR */}
      <div className="card p-3 grid gap-3 md:grid-cols-2 text-sm">
        <div>
          <div className="font-semibold mb-1">Observations</div>
          {(a.observations || []).map((o: any, i: number) => <div key={i} className="text-xs"><b>{o.by}</b>: {o.text}</div>)}
          {can("dispose_flags") && <div className="flex gap-1 mt-1"><input className="inp flex-1" value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Add an observation" />
            <button className="btn2" disabled={!obs} onClick={async () => { await api(`/applications/${id}/observations`, { json: { text: obs } }); setObs(""); load(); }}>Add</button></div>}
        </div>
        <div>
          <div className="font-semibold mb-1">Decision note</div>
          {a.decision ? <div className="text-xs">{a.decision.by}: {a.decision.text}</div> : (
            <>
              <textarea className="inp w-full" rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder={can("decision_note") ? "Record decision note" : "Senior officer only"} disabled={!can("decision_note")} />
              <button className="btn mt-1" disabled={!can("decision_note") || highOpen.length > 0 || !note} onClick={decide}
                title={highOpen.length ? `Open HIGH flags: ${highOpen.map((f: any) => f.id).join(", ")}` : ""}>Record decision note</button>
              {highOpen.length > 0 && <div className="text-xs text-amber-700 mt-1">Disabled until {highOpen.length} HIGH flag(s) are disposed: {highOpen.map((f: any) => f.id).join(", ")}</div>}
            </>
          )}
          {msg && <div className="text-xs mt-1">{msg}</div>}
          <div className="text-[11px] text-slate-500 mt-1">AI findings are decision support only. Statutory scrutiny and final decisions remain with the competent authority.</div>
        </div>
      </div>
    </div>
  );
}
