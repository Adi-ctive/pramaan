import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, Chip, SEV } from "../api";
import { useUser } from "../ctx";
import { AlertTriangle, ChevronRight, ShieldAlert, ShieldCheck } from "lucide-react";
import { CATEGORY, CHECKS } from "../labels";
import { CHECK_ICON, Tour } from "../ui";

function useData<T = any>(path: string, deps: any[] = []): [T | null, () => void, string] {
  const [d, setD] = useState<T | null>(null);
  const [err, setErr] = useState("");
  const load = () => api<T>(path).then(setD).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, deps);
  return [d, load, err];
}

function Bars({ data, color = "bg-blue-700" }: { data: Record<string, number>; color?: string }) {
  const max = Math.max(1, ...Object.values(data || {}));
  return (
    <div className="space-y-1">
      {Object.entries(data || {}).map(([k, v]) => (
        <div key={k} className="flex items-center gap-2 text-xs">
          <span className="w-40 truncate" title={k}>{k}</span>
          <div className="flex-1 bg-slate-100 dark:bg-slate-800 rounded h-3"><div className={`${color} h-3 rounded`} style={{ width: `${(v / max) * 100}%` }} /></div>
          <span className="w-6 text-right">{v}</span>
        </div>
      ))}
    </div>
  );
}

export function Queue() {
  const [rows] = useData<any[]>("/queue");
  const [q, setQ] = useState("");
  const [show, setShow] = useState<"all" | "review" | "clean">("all");
  const nav = useNavigate();
  if (!rows) return <div className="text-sm text-slate-500 p-6">Loading applications…</div>;
  const bad = (r: any) => r.counts.HIGH > 0, warn = (r: any) => !bad(r) && r.counts.MEDIUM > 0;
  const needs = rows.filter((r) => bad(r) || warn(r));
  const shown = rows.filter((r) => (show === "all" || (show === "review" ? bad(r) || warn(r) : !bad(r) && !warn(r))) &&
    (!q || `${r.institution} ${r.institution_id} ${r.external_ref}`.toLowerCase().includes(q.toLowerCase())));
  return (
    <div className="space-y-5 max-w-5xl">
      <Tour id="queue" steps={[
        { sel: "[data-tour=summary]", text: "Colleges send their approval documents. PRAMAAN checks every one before you open the file." },
        { sel: "[data-tour=card]", text: "Each card is one application. Red means serious problems were found. The little icons are the 9 checks." },
        { sel: "[data-tour=open]", text: "Click to open it. PRAMAAN walks you through each problem, one at a time." },
      ]} />
      <div data-tour="summary">
        <h1 className="text-3xl font-bold tracking-tight">Applications to review</h1>
        <p className="text-slate-500 mt-1">{needs.length ? `${needs.length} of ${rows.length} need your attention. The worst are on top.` : "Nothing needs attention right now."}</p>
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        {([["all", `All (${rows.length})`], ["review", `Needs review (${needs.length})`], ["clean", `Passed (${rows.length - needs.length})`]] as const).map(([k, l]) => (
          <button key={k} onClick={() => setShow(k)} className={`px-3 py-1.5 rounded-full text-sm border ${show === k ? "bg-slate-900 text-white border-slate-900 dark:bg-white dark:text-slate-900" : "bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700"}`}>{l}</button>
        ))}
        <div className="flex-1" />
        <input className="inp w-64" placeholder="Find a college" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="space-y-3">
        {shown.map((r, i) => {
          const Icon = bad(r) ? ShieldAlert : warn(r) ? AlertTriangle : ShieldCheck;
          const tone = bad(r) ? "bg-red-100 text-red-600 dark:bg-red-950" : warn(r) ? "bg-amber-100 text-amber-600 dark:bg-amber-950" : "bg-emerald-100 text-emerald-600 dark:bg-emerald-950";
          return (
            <div key={r.id} data-tour={i === 0 ? "card" : undefined} onClick={() => nav(`/app/${r.id}`)}
              className="card p-4 flex flex-wrap items-center gap-4 cursor-pointer hover:shadow-md hover:-translate-y-0.5 transition">
              <div className={`w-14 h-14 rounded-2xl grid place-items-center shrink-0 ${tone}`}><Icon size={30} strokeWidth={1.8} /></div>
              <div className="flex-1 min-w-[220px]">
                <div className="text-lg font-semibold leading-tight">{r.institution}</div>
                <div className={`text-sm font-medium mt-0.5 ${bad(r) ? "text-red-600" : warn(r) ? "text-amber-600" : "text-emerald-600"}`}>
                  {bad(r) ? `${r.counts.HIGH} serious problem${r.counts.HIGH > 1 ? "s" : ""}${r.counts.MEDIUM ? `, ${r.counts.MEDIUM} to check` : ""}` : warn(r) ? `${r.counts.MEDIUM} thing${r.counts.MEDIUM > 1 ? "s" : ""} to check` : "All 9 checks passed"}
                  {r.decided && <span className="text-slate-500 font-normal"> · decision recorded</span>}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">{CATEGORY[r.category] || r.category} · {r.host} · {r.region} region</div>
              </div>
              <div className="flex gap-1" aria-label="The 9 checks">
                {CHECKS.map((c) => {
                  const hits = (r.codes || []).filter(([code]: any) => c.codes.includes(code));
                  const CI = CHECK_ICON[c.key];
                  const col = hits.some(([, s]: any) => s === "HIGH") ? "text-red-600 bg-red-50 dark:bg-red-950" : hits.some(([, s]: any) => s === "MEDIUM") ? "text-amber-600 bg-amber-50 dark:bg-amber-950" : hits.length ? "text-sky-600 bg-sky-50 dark:bg-sky-950" : "text-emerald-600 bg-emerald-50 dark:bg-emerald-950";
                  return <span key={c.key} title={`${c.title}: ${hits.length ? `${hits.length} problem(s)` : "OK"}`} className={`w-7 h-7 rounded-lg grid place-items-center ${col}`}><CI size={15} /></span>;
                })}
              </div>
              <button data-tour={i === 0 ? "open" : undefined} className={`px-4 py-2 rounded-lg font-medium inline-flex items-center gap-1 ${bad(r) || warn(r) ? "bg-slate-900 text-white dark:bg-orange-500" : "border border-slate-300 dark:border-slate-600"}`}>
                {bad(r) || warn(r) ? "Review" : "View"} <ChevronRight size={16} /></button>
            </div>
          );
        })}
        {!shown.length && <div className="card p-6 text-center text-slate-500">No applications match.</div>}
      </div>
    </div>
  );
}

export function Dashboard() {
  const [d] = useData<any>("/dashboard");
  if (!d) return null;
  const k = d.kpi;
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold tracking-tight">Overview</h1><p className="text-sm text-slate-500 -mt-2">How the whole queue looks right now.</p>
      <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
        {[["In queue", k.in_queue], ["Ready for review", k.ready], ["SLA breaches", k.sla_breaches], ["Pending verifications", k.pending_verifications], ["Avg processing", `${k.avg_processing_ms} ms`], ["Flags / application", k.flags_per_app]].map(([l, v]) => (
          <div key={l} className="card p-3"><div className="text-xs text-slate-500">{l}</div><div className="text-xl font-bold">{v}</div></div>
        ))}
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        <div className="card p-3"><div className="font-semibold text-sm mb-2">Flags by category</div><Bars data={d.by_category} /></div>
        <div className="card p-3"><div className="font-semibold text-sm mb-2">Top deficiency codes</div><Bars data={d.top_codes} color="bg-red-500" /></div>
        <div className="card p-3"><div className="font-semibold text-sm mb-2">Verification outcomes</div><Bars data={d.verification} color="bg-emerald-600" /></div>
        <div className="card p-3"><div className="font-semibold text-sm mb-2">Applications by region</div><Bars data={d.by_region} color="bg-slate-500" /></div>
        <div className="card p-3 md:col-span-2"><div className="font-semibold text-sm mb-2">Processing time per application (ms)</div><Bars data={Object.fromEntries(d.processing.map((p: any) => [p.id, p.ms || 0]))} color="bg-violet-600" /></div>
      </div>
    </div>
  );
}

export function Alerts() {
  const [rows, load] = useData<any[]>("/alerts");
  const user = useUser()!;
  if (!rows) return null;
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold tracking-tight">Alerts</h1><p className="text-sm text-slate-500 -mt-2">Raised automatically when a check finds something an officer must act on.</p>
      <div className="card overflow-x-auto"><table className="w-full text-sm"><thead><tr><th>Type</th><th>Severity</th><th>Institution</th><th>Notify</th><th>Channel</th><th>Due</th><th>Status</th><th></th></tr></thead><tbody>
        {rows.map((a) => (
          <tr key={a.id} className="border-t dark:border-slate-800"><td>{a.type}</td><td><Chip text={a.severity} cls={SEV[a.severity]} /></td>
            <td><Link className="text-blue-700 hover:underline" to={`/app/${a.app_id}`}>{a.institution}</Link></td><td className="text-xs">{a.notify.join(", ")}</td>
            <td className="text-xs">{a.channel.join(", ")}</td><td className="text-xs">{a.due.slice(0, 10)}</td><td>{a.status}</td>
            <td>{a.status === "OPEN" && user.caps.includes("dispose_flags") && <button className="btn2" onClick={async () => { await api(`/alerts/${a.id}/ack`, { method: "POST" }); load(); }}>Acknowledge</button>}</td></tr>
        ))}
      </tbody></table></div>
      <Outbox />
    </div>
  );
}

function lineDiff(a: string, b: string) {
  const A = a.split("\n"), B = new Set(b.split("\n")), SA = new Set(A);
  return [...A.filter((l) => !B.has(l)).map((l) => "- " + l), ...b.split("\n").filter((l) => !SA.has(l)).map((l) => "+ " + l)];
}

function Outbox() {
  const [mails] = useData<any[]>("/outbox");
  return (
    <div className="card p-3">
      <div className="font-semibold text-sm mb-1">Email outbox</div>
      <div className="text-xs text-slate-500 mb-2">Alert emails. Sent through SMTP when SMTP_HOST is set (e.g. Mailpit locally); otherwise kept here as the mail catcher.</div>
      {(mails || []).slice(0, 20).map((m) => <div key={m.id} className="text-xs border-t border-slate-100 dark:border-slate-800 py-1"><b>{m.subject}</b> · {m.ts.slice(0, 16)} · {m.channel}<div className="text-slate-500">{m.body}</div></div>)}
      {mails && !mails.length && <div className="text-xs">No alert emails yet.</div>}
    </div>
  );
}

function Issuers() {
  const [rows, load] = useData<any[]>("/issuers");
  const set = async (id: string, patch: any) => { await api(`/issuers/${id}`, { method: "PUT", json: patch }); load(); };
  return (
    <div className="card p-3 text-sm">
      <div className="font-semibold mb-1">Issuing offices (mock verification services)</div>
      <div className="text-xs text-slate-500 mb-2">Simulate downtime, slowness or mismatches to show how PRAMAAN routes to manual confirmation.</div>
      <table className="w-full text-xs"><tbody>{(rows || []).map((i) => (
        <tr key={i.id} className="border-t border-slate-100 dark:border-slate-800"><td>{i.name}</td>
          <td><label><input type="checkbox" checked={!!i.down} onChange={(e) => set(i.id, { down: e.target.checked })} /> down</label></td>
          <td><label><input type="checkbox" checked={!!i.force_mismatch} onChange={(e) => set(i.id, { force_mismatch: e.target.checked })} /> force mismatch</label></td>
          <td><select className="inp" value={i.latency_ms || 0} onChange={(e) => set(i.id, { latency_ms: +e.target.value })}>{[0, 500, 2000].map((v) => <option key={v} value={v}>{v} ms</option>)}</select></td></tr>
      ))}</tbody></table>
    </div>
  );
}

export function RulePacks() {
  const [packs, load] = useData<any[]>("/rulepacks");
  const [queue] = useData<any[]>("/rulepacks/sample-apps");
  const user = useUser()!;
  const [sel, setSel] = useState<any>(null);
  const [text, setText] = useState("");
  const [out, setOut] = useState<any>(null);
  const [appId, setAppId] = useState("");
  const edit = user.caps.includes("edit_rules");
  if (!packs) return null;
  const active = packs.filter((p) => p.status === "ACTIVE");
  const run = async (path: string, body: any) => { try { setOut(await api(path, { json: body })); } catch (e: any) { setOut({ errors: [e.message] }); } };
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold tracking-tight">Checklist rules</h1><p className="text-sm text-slate-500 -mt-2">Each portal has a rule pack: which documents are required, which fields to read and what counts as a problem. Edit, test on a real application, then activate. No code changes.</p>
      <div className="card overflow-x-auto"><table className="w-full text-sm"><thead><tr><th>Key</th><th>Version</th><th>Status</th><th>Created</th><th></th></tr></thead><tbody>
        {packs.map((p) => <tr key={p.key + p.version} className="border-t dark:border-slate-800"><td className="font-mono">{p.key}</td><td>{p.version}</td><td><Chip text={p.status} cls={p.status === "ACTIVE" ? "bg-emerald-100 text-emerald-800" : ""} /></td><td className="text-xs">{p.created?.slice(0, 16)}</td>
          <td><button className="btn2" onClick={() => { setSel(p); setText(p.yaml); setOut(null); }}>{edit ? "Edit" : "View"}</button></td></tr>)}
      </tbody></table></div>
      {sel && (
        <div className="grid lg:grid-cols-2 gap-3">
          <textarea className="inp font-mono text-xs w-full h-[60vh]" value={text} onChange={(e) => setText(e.target.value)} readOnly={!edit} spellCheck={false} />
          <div className="space-y-2">
            {edit ? (
              <div className="flex flex-wrap gap-2">
                <button className="btn2" onClick={() => run("/rulepacks/validate", { yaml: text })}>Validate</button>
                <button className="btn2" onClick={() => setOut({ diff: lineDiff(active.find((p) => p.key === sel.key)?.yaml || "", text) })}>Diff vs active</button>
                <select className="inp" value={appId} onChange={(e) => setAppId(e.target.value)}><option value="">Dry run on…</option>{(queue || []).filter((q: any) => q).map((q: any) => <option key={q.id} value={q.id}>{q.external_ref} - {q.institution}</option>)}</select>
                <button className="btn2" disabled={!appId} onClick={() => run("/rulepacks/dryrun", { yaml: text, app_id: appId })}>Dry run</button>
                <button className="btn" onClick={() => confirm("Activate this version? It becomes the active pack for new runs.") && run("/rulepacks/activate", { yaml: text }).then(load)}>Activate</button>
              </div>
            ) : <div className="text-xs text-slate-500">Read only. Rule Admin can edit, dry-run and activate.</div>}
            {out && <pre className="card p-3 text-xs whitespace-pre-wrap overflow-auto max-h-[55vh]">{out.diff ? out.diff.join("\n") || "No changes" : JSON.stringify(out, null, 2)}</pre>}
            <div className="text-xs text-slate-500">All numeric norms in demo packs are illustrative placeholders (demo_value: true), not real handbook figures.</div>
          </div>
        </div>
      )}
    </div>
  );
}

export function Hosts() {
  const [hosts, load, err] = useData<any[]>("/hosts");
  const [key, setKey] = useState<any>(null);
  if (err) return <div className="text-sm">{err}</div>;
  if (!hosts) return null;
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold tracking-tight">Connected portals</h1><p className="text-sm text-slate-500 -mt-2">Portals that send applications to PRAMAAN. Each maps its own upload slots to PRAMAAN document types and receives signed status updates.</p>
      <Issuers />
      {key && <div className="card p-3 text-sm bg-amber-50 dark:bg-amber-950">New API key (shown once): <code className="break-all">{key.api_key}</code><div className="text-xs">{key.note}</div></div>}
      {hosts.map((h) => (
        <div key={h.id} className="card p-3 space-y-2 text-sm">
          <div className="flex flex-wrap items-center gap-2"><b>{h.name}</b><Chip text={h.id} /><span className="text-xs font-mono">key {h.key_prefix}…</span><span className="text-xs">pack {h.pack_key}</span>
            <div className="flex-1" />
            <button className="btn2" onClick={async () => setKey(await api(`/hosts/${h.id}/rotate`, { method: "POST" }))}>Rotate key</button>
            <button className="btn2" onClick={async () => { await api(`/hosts/${h.id}/test-webhook`, { method: "POST" }); load(); }}>Send test webhook</button></div>
          <div className="text-xs">Webhook: <code>{h.webhook_url}</code> (HMAC-SHA256 in X-Pramaan-Signature)</div>
          <div className="grid md:grid-cols-2 gap-3">
            <div><div className="font-semibold text-xs mb-1">Slot mapping (host slot ↔ canonical)</div>
              <table className="w-full text-xs"><tbody>{h.slots.map((s: any) => <tr key={s[0]} className="border-t dark:border-slate-800"><td className="font-mono">{s[0]}</td><td>{s[1]}</td><td>→</td><td className="font-mono">{s[2]}</td></tr>)}</tbody></table>
              <a className="text-xs text-blue-700 underline" href={h.id === "HOST-A" ? "/host-a/" : "/host-b/"} target="_blank">Preview widget on this host</a></div>
            <div><div className="font-semibold text-xs mb-1">Delivery log</div>
              <table className="w-full text-xs"><tbody>{h.deliveries.map((d: any) => <tr key={d.id} className="border-t dark:border-slate-800"><td>{d.ts.slice(5, 19)}</td><td>{d.event}</td><td>{d.status}</td><td>{d.attempts}x</td></tr>)}</tbody></table></div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function Audit() {
  const [rows, load] = useData<any[]>("/audit");
  const [v, setV] = useState<any>(null);
  if (!rows) return null;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2"><h1 className="text-2xl font-bold tracking-tight mr-auto">Audit trail</h1>
        <button className="btn" onClick={async () => { setV(await api("/audit/verify")); load(); }}>Verify chain</button>
        <a className="btn2" href="/api/audit/export">Export CSV</a></div>
      <p className="text-sm text-slate-500 -mt-2 w-full">Every action is chained to the previous one with a hash. If anyone edits a past row, verification fails at that row.</p>
      {v && <div className={`card p-3 text-sm ${v.ok ? "bg-emerald-50 dark:bg-emerald-950" : "bg-red-50 dark:bg-red-950"}`}>{v.ok ? `Chain intact. Last verified sequence #${v.last_verified}.` : `Chain BROKEN at sequence #${v.broken_at}. Last good #${v.last_verified}.`}</div>}
      <div className="card overflow-x-auto"><table className="w-full text-xs"><thead><tr><th>#</th><th>Time</th><th>Actor</th><th>Action</th><th>Object</th><th>Hash</th></tr></thead><tbody>
        {rows.map((e) => <tr key={e.seq} className="border-t dark:border-slate-800"><td>{e.seq}</td><td className="whitespace-nowrap">{e.ts.slice(0, 19).replace("T", " ")}</td><td>{e.actor}</td><td>{e.action}</td><td className="font-mono">{e.object}</td><td className="font-mono">{e.hash.slice(0, 12)}</td></tr>)}
      </tbody></table></div>
    </div>
  );
}

export function Evaluation() {
  const [runs, load] = useData<any[]>("/eval/runs");
  const user = useUser()!;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [pick, setPick] = useState(0);
  if (!runs) return null;
  const r = runs[pick] || runs[0];
  const pct = (x: any) => (x == null ? "n/a" : `${Math.round(x * 1000) / 10}%`);
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2"><h1 className="text-2xl font-bold tracking-tight mr-auto">Accuracy on the test set</h1>
        {user.caps.includes("run_eval") && <button className="btn" disabled={busy} onClick={async () => { setBusy(true); setErr(""); try { await api("/eval/run?quick=true", { method: "POST" }); load(); } catch (e: any) { setErr(e.message); } setBusy(false); }}>{busy ? "Running…" : "Run quick evaluation"}</button>}</div>
      <p className="text-sm text-slate-500 -mt-2">Measured on freshly generated synthetic documents with known answers. Real numbers, including weak ones.</p>
      {err && <div className="text-sm text-red-600">{err}</div>}
      {!r ? <div className="card p-3 text-sm">No runs yet.</div> : (
        <>
          {runs.length > 1 && (
            <select className="inp" value={pick} onChange={(e) => setPick(+e.target.value)}>
              {runs.map((x, i) => <option key={x.id} value={i}>{x.created.slice(0, 16).replace("T", " ")} · {x.mode} mode · {x.validation ? "full run" : "quick run"}</option>)}
            </select>
          )}
          <div className="text-xs text-slate-500">Run {r.id} · {r.created.slice(0, 16)} · {r.mode} mode · {r.samples_per_class} samples per class · {r.eval_seconds}s. Synthetic test set; real measured numbers.</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {[["Field exact match", pct(r.extraction.field_exact_match), `${r.extraction.fields} fields, printed digital`],
              ["Printed CER", pct(r.extraction.printed_cer), "character error rate"],
              ["Handwriting CER", r.extraction.handwriting_cer == null ? "not measured" : pct(r.extraction.handwriting_cer), r.extraction.handwriting_note],
              ["Discrepancy recall", pct(r.discrepancies.recall), `${r.discrepancies.found}/${r.discrepancies.expected} seeded; ${r.discrepancies.golden_high_medium_flags} HIGH/MED on golden`],
              ["Source verification success", pct(r.verification.success_rate), `${r.verification.verifiable} verifiable, ${r.verification.manual_review} manual; mismatch caught: ${r.verification.mismatch_caught}`],
              ["Avg time / application", `${r.timing.avg_ms_per_application} ms`, `${r.timing.avg_ms_per_document} ms per document`],
              ["Alert timeliness", `${r.alerts.avg_delay_ms} ms`, r.alerts.note],
              ["Est. manual effort saved", pct(r.effort.estimated_reduction), `${r.effort.formula}; baseline ${r.effort.baseline_min_per_doc} min/doc, ${r.effort.officer_min_per_flag} min/flag (assumptions)`],
              ["Lab count MAE", String(r.infrastructure.count_mae), `${r.infrastructure.photos} photos · ${r.infrastructure.detector}`]].map(([l, v, s]) => (
              <div key={l} className="card p-3"><div className="text-xs text-slate-500">{l}</div><div className="text-xl font-bold">{v}</div><div className="text-[11px] text-slate-500">{s}</div></div>
            ))}
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            <div className="card overflow-x-auto"><div className="font-semibold text-sm p-3 pb-0">Anomaly detection per forgery type</div><table className="w-full text-xs"><thead><tr><th>Type</th><th>P</th><th>R</th><th>F1</th><th>TP/FP/FN</th></tr></thead><tbody>
              {Object.entries(r.anomaly).map(([k, m]: any) => <tr key={k} className="border-t dark:border-slate-800"><td>{k}</td><td>{m.precision}</td><td>{m.recall}</td><td>{m.f1}</td><td>{m.tp}/{m.fp}/{m.fn}</td></tr>)}
            </tbody></table></div>
            <div className="card overflow-x-auto"><div className="font-semibold text-sm p-3 pb-0">Extraction per document type</div><table className="w-full text-xs"><thead><tr><th>Type</th><th>Docs</th><th>Classified</th><th>Fields exact</th></tr></thead><tbody>
              {Object.entries(r.extraction.per_type).map(([k, m]: any) => <tr key={k} className="border-t dark:border-slate-800"><td>{k}</td><td>{m.docs}</td><td>{m.classified_ok}/{m.docs}</td><td>{m.exact}/{m.fields}</td></tr>)}
            </tbody></table></div>
            <div className="card overflow-x-auto md:col-span-2"><div className="font-semibold text-sm p-3 pb-0">Seeded applications: expected vs found</div><table className="w-full text-xs"><thead><tr><th>Application</th><th>Expected</th><th>Missed</th><th>Other flags</th></tr></thead><tbody>
              {r.discrepancies.per_application.map((a: any) => <tr key={a.application} className="border-t dark:border-slate-800"><td>{a.application}</td><td>{a.expected.join(", ") || "-"}</td><td className="text-red-600">{a.missed.join(", ") || "none"}</td><td>{a.extra.join(", ") || "-"}</td></tr>)}
            </tbody></table></div>
          </div>
        </>
      )}
    </div>
  );
}
