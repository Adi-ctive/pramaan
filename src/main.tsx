import React, { useContext, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { BarChart3, Bell, ChevronRight, ClipboardList, FileCheck2, Gavel, Inbox, MapPin, Plug, ScanSearch, ShieldCheck, Upload } from "lucide-react";
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
  const [totp, setTotp] = useState<string | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api("/demo-users").then(setDemo).catch(() => {}); }, []);
  const enter = async (username: string) => {
    try { await api("/auth/demo-login", { json: { username } }); onDone(); } catch (x: any) { setErr(x.message); }
  };
  const login = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await api("/auth/login", { json: { username: u, password: p, ...(totp ? { totp } : {}) } }); onDone(); }
    catch (x: any) { if (x.message === "totp_required") { setTotp(""); setErr("Enter the 6-digit code from your authenticator app."); } else setErr(x.message); }
  };
  const others = DEMO_ORDER.slice(1).map((n) => demo.find((d) => d.username === n)).filter(Boolean);
  const flow = [
    { icon: Upload, title: "College uploads", text: "on its usual portal" },
    { icon: ScanSearch, title: "PRAMAAN checks", text: "9 checks in seconds" },
    { icon: MapPin, title: "Problems pinned", text: "on the exact spot" },
    { icon: Gavel, title: "Officer decides", text: "one problem at a time" },
  ];
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="max-w-6xl mx-auto px-4 py-5 flex items-center gap-3">
        <Logo /><div className="font-extrabold tracking-tight text-lg">PRAMAAN</div>
        <span className="text-xs text-slate-400 hidden sm:inline">Smart India Hackathon 2026 · SIH26261</span>
      </div>
      <section className="max-w-5xl mx-auto px-4 pt-10 text-center">
        <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight leading-[1.05]">Catch problems in approval documents<br className="hidden md:block" /> <span className="text-orange-400">before</span> anyone opens the file.</h1>
        <p className="mt-5 text-slate-300 text-lg max-w-2xl mx-auto">AI checks every document a college sends to AICTE and points to exactly what is wrong. Officers make every decision.</p>
      </section>

      <section className="max-w-5xl mx-auto px-4 mt-10 grid md:grid-cols-2 gap-4">
        <button onClick={() => enter("senior")} className="group text-left rounded-3xl bg-white text-slate-900 p-7 shadow-2xl hover:-translate-y-1 transition">
          <div className="w-14 h-14 rounded-2xl bg-orange-100 text-orange-600 grid place-items-center"><Gavel size={28} /></div>
          <div className="text-2xl font-bold mt-4">I review applications</div>
          <div className="text-slate-500 mt-1">See what PRAMAAN found, problem by problem, and decide.</div>
          <div className="mt-5 inline-flex items-center gap-1 font-semibold text-orange-600 group-hover:gap-2 transition-all">Enter as Senior Officer <ChevronRight size={18} /></div>
        </button>
        <a href="/host-a/" className="group text-left rounded-3xl bg-white/5 border border-white/15 p-7 hover:bg-white/10 hover:-translate-y-1 transition">
          <div className="w-14 h-14 rounded-2xl bg-white/10 text-white grid place-items-center"><Upload size={28} /></div>
          <div className="text-2xl font-bold mt-4">I'm a college</div>
          <div className="text-slate-300 mt-1">Upload documents on a sample portal and get instant feedback.</div>
          <div className="mt-5 inline-flex items-center gap-1 font-semibold text-orange-300 group-hover:gap-2 transition-all">Open the college portal <ChevronRight size={18} /></div>
        </a>
      </section>
      {err && <div className="text-center text-sm text-red-400 mt-3">{err}</div>}

      <section className="max-w-5xl mx-auto px-4 mt-14">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {flow.map((f, i) => (
            <div key={f.title} className="relative rounded-2xl bg-white/5 border border-white/10 p-4 text-center">
              <div className="mx-auto w-12 h-12 rounded-full bg-orange-500/15 text-orange-300 grid place-items-center"><f.icon size={22} /></div>
              <div className="font-semibold mt-3">{f.title}</div>
              <div className="text-sm text-slate-400">{f.text}</div>
              {i < flow.length - 1 && <ChevronRight className="hidden md:block absolute -right-4 top-1/2 -translate-y-1/2 text-slate-600" />}
            </div>
          ))}
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-4 mt-12 pb-14 grid md:grid-cols-2 gap-6 text-sm">
        <details className="rounded-2xl bg-white/5 border border-white/10 p-4">
          <summary className="cursor-pointer font-semibold">Other demo roles</summary>
          <div className="mt-3 space-y-2">
            {others.map((d: any) => (
              <button key={d.username} onClick={() => enter(d.username)} className="w-full text-left rounded-xl bg-white/5 hover:bg-white/10 p-3">
                <div className="font-medium">{ROLES[d.role]?.name}{d.username === "officer.west" ? " (West region)" : ""}</div>
                <div className="text-slate-400 text-xs">{ROLES[d.role]?.does}</div>
              </button>
            ))}
          </div>
        </details>
        <details className="rounded-2xl bg-white/5 border border-white/10 p-4">
          <summary className="cursor-pointer font-semibold">Sign in with a password</summary>
          <form onSubmit={login} className="mt-3 space-y-2 text-slate-900">
            <input className="inp w-full" placeholder="Username" value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" />
            <input className="inp w-full" placeholder="Password" type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" />
            {totp !== null && <input className="inp w-full" placeholder="Authenticator code" inputMode="numeric" value={totp} onChange={(e) => setTotp(e.target.value)} autoComplete="one-time-code" />}
            <button className="btn w-full">Sign in</button>
          </form>
        </details>
        <p className="md:col-span-2 text-xs text-slate-500 text-center">All colleges, issuers and documents here are fictional. Findings are decision support only.</p>
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

function TwoStep({ onClose }: { onClose: () => void }) {
  const { user, reload } = useContext(Ctx);
  const [setup, setSetup] = useState<any>(null);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const go = async (path: string) => {
    try { await api(path, { json: { code } }); setMsg(path.endsWith("enable") ? "Two-step sign-in is on. You'll be asked for a code at sign-in." : "Two-step sign-in is off."); setCode(""); setSetup(null); reload(); }
    catch (e: any) { setMsg(e.message); }
  };
  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-black/30 p-4" onClick={onClose}>
      <div className="card w-full max-w-sm p-5 space-y-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center"><div className="font-bold flex-1">Two-step sign-in</div><button className="btn2" onClick={onClose}>Close</button></div>
        <p className="text-sm text-slate-600 dark:text-slate-300">Adds a 6-digit code from an authenticator app (Google Authenticator, Microsoft Authenticator, etc.) to password sign-in.</p>
        {user?.mfa ? (
          <>
            <div className="text-sm font-medium text-emerald-700">Status: on</div>
            <input className="inp w-full" placeholder="Current 6-digit code to turn it off" value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" />
            <button className="btn2" disabled={code.length < 6} onClick={() => go("/auth/totp/disable")}>Turn off</button>
          </>
        ) : !setup ? (
          <button className="btn" onClick={async () => setSetup(await api("/auth/totp/setup", { method: "POST" }))}>Set up</button>
        ) : (
          <>
            <img src={setup.qr} alt="QR code for the authenticator app" className="mx-auto w-44 h-44" />
            <div className="text-xs text-slate-500 break-all">Or enter this key: <code>{setup.secret}</code></div>
            <input className="inp w-full" placeholder="6-digit code from the app" value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" />
            <button className="btn" disabled={code.length < 6} onClick={() => go("/auth/totp/enable")}>Confirm and turn on</button>
          </>
        )}
        {msg && <div className="text-sm">{msg}</div>}
      </div>
    </div>
  );
}

function Badges() {
  const [h, setH] = useState<any>(null);
  useEffect(() => { const f = () => api("/health").then(setH).catch(() => {}); f(); const t = setInterval(f, 30000); return () => clearInterval(t); }, []);
  if (!h) return null;
  const on = h.agent_mode === "on" && h.agents;
  return (
    <div className="hidden md:flex items-center gap-1 text-[11px]">
      <span title="AGENT_MODE on this server" className={`px-2 py-0.5 rounded-full border ${on ? "border-violet-300 text-violet-700 dark:text-violet-300" : "border-slate-300 text-slate-500"}`}>Agents: {on ? "on" : "off"} ({h.mode})</span>
      <span title={h.local_ai?.online ? `Local AI worker ${h.local_ai.model}` : "No local AI worker connected"} className={`px-2 py-0.5 rounded-full border ${h.local_ai?.online ? "border-emerald-300 text-emerald-700 dark:text-emerald-300" : "border-slate-300 text-slate-500"}`}>
        Local AI: {h.local_ai?.online ? "online" : "offline"}</span>
    </div>
  );
}

function Shell() {
  const { user, setUser, reload } = useContext(Ctx);
  const [guide, setGuide] = useState(false);
  const [twoStep, setTwoStep] = useState(false);
  const [dark, setDark] = useState(() => { try { return localStorage.getItem("dark") === "1"; } catch { return false; } });
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); try { localStorage.setItem("dark", dark ? "1" : "0"); } catch {} }, [dark]);
  if (!user) return null;
  const c = user.caps;
  const nav = [
    ["/", "Applications", c.includes("view_queue"), Inbox], ["/dashboard", "Overview", c.includes("view_queue"), BarChart3], ["/alerts", "Alerts", c.includes("view_queue"), Bell],
    ["/evaluation", "Accuracy", true, FileCheck2], ["/rules", "Checklist rules", true, ClipboardList], ["/hosts", "Connected portals", c.includes("manage_hosts"), Plug],
    ["/audit", "Audit trail", c.includes("audit"), ShieldCheck],
  ].filter((x) => x[2]) as [string, string, boolean, any][];
  const home = c.includes("view_queue") ? "/" : c.includes("manage_hosts") ? "/hosts" : "/rules";
  const switchTo = async (username: string) => { await api("/auth/demo-login", { json: { username } }); reload(); };
  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <aside className="md:w-56 shrink-0 bg-slate-950 text-slate-300 p-3 flex md:flex-col gap-1 overflow-x-auto">
        <Link to="/" className="hidden md:flex items-center gap-2 mb-6 mt-1 px-1"><Logo size={8} /><div className="font-extrabold text-white tracking-tight">PRAMAAN</div></Link>
        {nav.map(([to, label, , Icon]) => (
          <NavLink key={to} to={to} end className={({ isActive }) => `px-3 py-2 rounded-lg text-sm whitespace-nowrap inline-flex items-center gap-2 ${isActive ? "bg-white/10 text-white font-semibold" : "hover:bg-white/5 hover:text-white"}`}><Icon size={16} />{label}</NavLink>
        ))}
        <div className="hidden md:block flex-1" />
        <button onClick={() => setGuide(true)} className="hidden md:block text-left px-3 py-2 rounded-lg text-sm bg-orange-500/15 text-orange-300 hover:bg-orange-500/25">Demo guide</button>
      </aside>
      <div className="flex-1 min-w-0">
        <header className="flex flex-wrap items-center gap-2 px-4 py-2.5 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 text-sm">
          <button onClick={() => setGuide(true)} className="md:hidden btn2">Guide</button>
          <button onClick={() => window.dispatchEvent(new Event("pramaan:tour"))} className="btn2 border-orange-300 text-orange-700 dark:text-orange-300">Show me around</button>
          <div className="flex-1" />
          <Badges />
          <label className="text-xs text-slate-500 hidden sm:block">Viewing as</label>
          <select className="inp" value={user.sub} onChange={(e) => switchTo(e.target.value)} title="Switch demo role">
            {DEMO_ORDER.concat(user.sub && !DEMO_ORDER.includes(user.sub) ? [user.sub] : []).map((n) => <option key={n} value={n}>{n === user.sub ? `${ROLES[user.role]?.name || user.role}${user.region !== "ALL" ? ` (${user.region})` : ""}` : n}</option>)}
          </select>
          <button className="btn2" onClick={() => setTwoStep(true)}>{user.mfa ? "2-step: on" : "2-step sign-in"}</button>
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
      {twoStep && <TwoStep onClose={() => setTwoStep(false)} />}
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
