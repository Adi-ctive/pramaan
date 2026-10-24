import React, { useContext, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { api } from "./api";
import { Ctx, User } from "./ctx";
import { DEMO_STEPS, ROLES } from "./labels";
import Detail from "./pages/Detail";
import { Alerts, Audit, Dashboard, Evaluation, Hosts, Queue, RulePacks } from "./pages/Pages";

function Logo(_: { size?: number }) {
  return (
    <div className={`w-9 h-9 rounded-xl bg-gradient-to-br from-orange-500 to-amber-400 grid place-items-center text-white shadow`}>
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="3"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
    </div>
  );
}

const DEMO_ORDER = ["senior", "officer.west", "ruleadmin", "integration", "auditor"];

function Landing({ onDone }: { onDone: () => void }) {
  const [demo, setDemo] = useState<any[]>([]);
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => { api("/demo-users").then(setDemo).catch(() => {}); }, []);
  const enter = async (username: string) => {
    try { await api("/auth/demo-login", { json: { username } }); onDone(); } catch (x: any) { setErr(x.message); }
  };
  const login = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await api("/auth/login", { json: { username: u, password: p } }); onDone(); } catch (x: any) { setErr(x.message); }
  };
  const users = DEMO_ORDER.map((n) => demo.find((d) => d.username === n)).filter(Boolean);
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="max-w-6xl mx-auto px-4 py-6 flex items-center gap-3">
        <Logo /><div className="font-extrabold tracking-tight text-lg">PRAMAAN</div>
        <span className="text-xs text-slate-400 hidden sm:inline">Smart India Hackathon 2026 · SIH26261</span>
        <div className="flex-1" />
        <a href="/host-a/" className="text-sm text-slate-300 hover:text-white">Institution portal (mock)</a>
      </div>
      <section className="max-w-6xl mx-auto px-4 pt-8 pb-12 grid lg:grid-cols-[1.2fr_1fr] gap-10 items-center">
        <div>
          <div className="inline-block text-xs font-semibold px-2 py-1 rounded-full bg-orange-500/15 text-orange-300 mb-4">AI-assisted scrutiny for AICTE approvals</div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight leading-tight">Every document checked<br />before an officer opens the file.</h1>
          <p className="mt-4 text-slate-300 text-lg max-w-xl">
            Institutions upload approval documents. PRAMAAN reads them, checks them against the rules and AICTE records, confirms them with the issuing office,
            and shows officers exactly what is wrong and where. Officers still make every decision.
          </p>
          <div className="mt-6 grid sm:grid-cols-3 gap-3 text-sm">
            {[["1", "Institution uploads", "on its usual portal, through a small PRAMAAN widget"], ["2", "PRAMAAN checks", "9 kinds of checks in seconds, each with evidence"], ["3", "Officer reviews", "worst cases first, confirms or dismisses each finding"]].map(([n, t, d]) => (
              <div key={n} className="rounded-xl bg-white/5 border border-white/10 p-3">
                <div className="text-orange-300 font-bold">{n}</div><div className="font-semibold">{t}</div><div className="text-slate-400 text-xs mt-1">{d}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl bg-white text-slate-900 p-5 shadow-2xl">
          <div className="font-bold text-lg">Try the live demo</div>
          <div className="text-sm text-slate-500 mb-3">One click, no password. All institutions, issuers and documents are fictional.</div>
          <div className="space-y-2">
            {users.map((d: any) => (
              <button key={d.username} onClick={() => enter(d.username)} className="w-full text-left rounded-xl border border-slate-200 hover:border-orange-400 hover:bg-orange-50 p-3 transition">
                <div className="font-semibold">Enter as {ROLES[d.role]?.name || d.role}{d.username === "officer.west" ? " (West)" : ""}</div>
                <div className="text-xs text-slate-500">{ROLES[d.role]?.does}</div>
              </button>
            ))}
            <a href="/host-a/" className="block rounded-xl border border-slate-200 hover:border-orange-400 hover:bg-orange-50 p-3">
              <div className="font-semibold">Upload as an institution</div><div className="text-xs text-slate-500">{ROLES.INSTITUTION.does}</div>
            </a>
          </div>
          {err && <div className="text-sm text-red-600 mt-2">{err}</div>}
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer text-slate-500">Sign in with a password</summary>
            <form onSubmit={login} className="mt-2 space-y-2">
              <input className="inp w-full" placeholder="Username" value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" />
              <input className="inp w-full" placeholder="Password" type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" />
              <button className="btn w-full">Sign in</button>
            </form>
          </details>
        </div>
      </section>
      <section className="bg-slate-900 border-t border-white/10">
        <div className="max-w-6xl mx-auto px-4 py-10">
          <h2 className="text-xl font-bold mb-4">What the demo shows</h2>
          <ol className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {DEMO_STEPS.map((s, i) => (
              <li key={i} className="rounded-xl bg-white/5 border border-white/10 p-3 text-sm">
                <div className="text-orange-300 text-xs font-bold">STEP {i + 1}</div><div className="font-semibold">{s.title}</div><div className="text-slate-400 text-xs mt-1">{s.body}</div>
              </li>
            ))}
          </ol>
          <p className="text-xs text-slate-500 mt-6">Prototype. Findings are decision support only. Statutory scrutiny, inspections and final decisions stay with the competent authority.</p>
        </div>
      </section>
    </div>
  );
}

function Guide({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <div className="w-full max-w-md h-full bg-white dark:bg-slate-900 p-5 overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center mb-3"><div className="font-bold text-lg flex-1">Demo guide</div><button className="btn2" onClick={onClose}>Close</button></div>
        <ol className="space-y-3">
          {DEMO_STEPS.map((s, i) => (
            <li key={i} className="flex gap-3">
              <div className="w-7 h-7 shrink-0 rounded-full bg-orange-100 text-orange-700 grid place-items-center text-sm font-bold">{i + 1}</div>
              <div className="text-sm"><div className="font-semibold">{s.title}</div><div className="text-slate-600 dark:text-slate-400">{s.body}</div>
                {s.link && (s.link.startsWith("/host") ? <a className="text-orange-600 font-medium" href={s.link}>{s.linkText} →</a> : <Link className="text-orange-600 font-medium" to={s.link} onClick={onClose}>{s.linkText} →</Link>)}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

function Shell() {
  const { user, setUser, reload } = useContext(Ctx);
  const [guide, setGuide] = useState(false);
  const [dark, setDark] = useState(() => { try { return localStorage.getItem("dark") === "1"; } catch { return false; } });
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); try { localStorage.setItem("dark", dark ? "1" : "0"); } catch {} }, [dark]);
  if (!user) return null;
  const c = user.caps;
  const nav = [
    ["/", "Applications", c.includes("view_queue")], ["/dashboard", "Overview", c.includes("view_queue")], ["/alerts", "Alerts", c.includes("view_queue")],
    ["/evaluation", "Accuracy", true], ["/rules", "Checklist rules", true], ["/hosts", "Connected portals", c.includes("manage_hosts")],
    ["/audit", "Audit trail", c.includes("audit")],
  ].filter((x) => x[2]) as [string, string][];
  const home = c.includes("view_queue") ? "/" : c.includes("manage_hosts") ? "/hosts" : "/rules";
  const switchTo = async (username: string) => { await api("/auth/demo-login", { json: { username } }); reload(); };
  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <aside className="md:w-56 shrink-0 bg-slate-950 text-slate-300 p-3 flex md:flex-col gap-1 overflow-x-auto">
        <Link to="/" className="hidden md:flex items-center gap-2 mb-6 mt-1 px-1"><Logo size={8} /><div className="font-extrabold text-white tracking-tight">PRAMAAN</div></Link>
        {nav.map(([to, label]) => (
          <NavLink key={to} to={to} end className={({ isActive }) => `px-3 py-2 rounded-lg text-sm whitespace-nowrap ${isActive ? "bg-white/10 text-white font-semibold" : "hover:bg-white/5 hover:text-white"}`}>{label}</NavLink>
        ))}
        <div className="hidden md:block flex-1" />
        <button onClick={() => setGuide(true)} className="hidden md:block text-left px-3 py-2 rounded-lg text-sm bg-orange-500/15 text-orange-300 hover:bg-orange-500/25">Demo guide</button>
      </aside>
      <div className="flex-1 min-w-0">
        <header className="flex flex-wrap items-center gap-2 px-4 py-2.5 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 text-sm">
          <button onClick={() => setGuide(true)} className="md:hidden btn2">Guide</button>
          <div className="flex-1" />
          <label className="text-xs text-slate-500 hidden sm:block">Viewing as</label>
          <select className="inp" value={user.sub} onChange={(e) => switchTo(e.target.value)} title="Switch demo role">
            {DEMO_ORDER.concat(user.sub && !DEMO_ORDER.includes(user.sub) ? [user.sub] : []).map((n) => <option key={n} value={n}>{n === user.sub ? `${ROLES[user.role]?.name || user.role}${user.region !== "ALL" ? ` (${user.region})` : ""}` : n}</option>)}
          </select>
          <button className="btn2" onClick={() => setDark(!dark)}>{dark ? "Light" : "Dark"}</button>
          <button className="btn2" onClick={async () => { await api("/auth/logout", { method: "POST" }); setUser(null); }}>Exit</button>
        </header>
        <main className="p-4 md:p-6 max-w-[1500px]">
          <Routes>
            <Route path="/" element={c.includes("view_queue") ? <Queue /> : <Navigate to={home} />} />
            <Route path="/app/:id" element={<Detail />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/evaluation" element={<Evaluation />} />
            <Route path="/rules" element={<RulePacks />} />
            <Route path="/hosts" element={<Hosts />} />
            <Route path="/audit" element={<Audit />} />
          </Routes>
        </main>
      </div>
      {guide && <Guide onClose={() => setGuide(false)} />}
    </div>
  );
}

function Root() {
  const [user, setUser] = useState<User>(null);
  const [ready, setReady] = useState(false);
  const load = () => api("/me").then(setUser).catch(() => setUser(null)).finally(() => setReady(true));
  useEffect(() => { load(); }, []);
  if (!ready) return null;
  return (
    <Ctx.Provider value={{ user, setUser, reload: load }}>
      <BrowserRouter>{user ? <Shell /> : <Landing onDone={load} />}</BrowserRouter>
    </Ctx.Provider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<Root />);
