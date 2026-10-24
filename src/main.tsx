import React, { createContext, useContext, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { api } from "./api";
import Detail from "./pages/Detail";
import { Alerts, Audit, Dashboard, Evaluation, Hosts, Queue, RulePacks } from "./pages/Pages";

type User = { sub: string; role: string; region: string; caps: string[] } | null;
const Ctx = createContext<{ user: User; setUser: (u: User) => void }>({ user: null, setUser: () => {} });
export const useUser = () => useContext(Ctx).user;

function Login({ onDone }: { onDone: () => void }) {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");
  const [demo, setDemo] = useState<any[]>([]);
  useEffect(() => { api("/demo-users").then(setDemo).catch(() => {}); }, []);
  const go = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    try { await api("/auth/login", { json: { username: u, password: p } }); onDone(); } catch (x: any) { setErr(x.message); }
  };
  return (
    <div className="min-h-screen grid place-items-center p-4">
      <form onSubmit={go} className="card p-6 w-full max-w-sm space-y-3">
        <div className="flex items-center gap-2"><Logo /><div><div className="font-bold">PRAMAAN</div><div className="text-xs text-slate-500">Application validation console (prototype)</div></div></div>
        <input className="inp w-full" placeholder="Username" value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" />
        <input className="inp w-full" placeholder="Password" type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" />
        {err && <div className="text-sm text-red-600">{err}</div>}
        <button className="btn w-full">Sign in</button>
        {demo.length > 0 && (
          <div className="text-xs text-slate-500 border-t pt-3 dark:border-slate-800">
            <div className="font-semibold mb-1">Demo users (synthetic data only)</div>
            {demo.map((d) => (
              <button type="button" key={d.username} onClick={() => setU(d.username)} className="block hover:underline">{d.username} - {d.role}</button>
            ))}
          </div>
        )}
        <div className="text-[11px] text-slate-400">Mock portals: <a className="underline" href="/host-a/">Host A</a> · <a className="underline" href="/host-b/">Host B</a></div>
      </form>
    </div>
  );
}

function Logo() {
  return <div className="w-8 h-8 rounded-lg bg-blue-900 grid place-items-center text-white font-bold">✓</div>;
}

function Shell() {
  const { user, setUser } = useContext(Ctx);
  const [health, setHealth] = useState<any>({});
  const [dark, setDark] = useState(() => { try { return localStorage.getItem("dark") === "1"; } catch { return false; } });
  useEffect(() => { api("/health").then(setHealth).catch(() => {}); }, []);
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); try { localStorage.setItem("dark", dark ? "1" : "0"); } catch {} }, [dark]);
  if (!user) return null;
  const c = user.caps;
  const nav = [
    ["/", "Queue", c.includes("view_queue")], ["/dashboard", "Dashboard", c.includes("view_queue")], ["/alerts", "Alerts", c.includes("view_queue")],
    ["/evaluation", "Evaluation", true], ["/rules", "Rule packs", true], ["/hosts", "Hosts & keys", c.includes("manage_hosts")],
    ["/audit", "Audit", c.includes("audit")],
  ].filter((x) => x[2]) as [string, string][];
  const home = c.includes("view_queue") ? "/" : c.includes("manage_hosts") ? "/hosts" : "/rules";
  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <aside className="md:w-52 shrink-0 border-b md:border-b-0 md:border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3 flex md:flex-col gap-1 overflow-x-auto">
        <div className="hidden md:flex items-center gap-2 mb-4"><Logo /><div className="font-bold">PRAMAAN</div></div>
        {nav.map(([to, label]) => (
          <NavLink key={to} to={to} end className={({ isActive }) => `px-3 py-1.5 rounded-md text-sm whitespace-nowrap ${isActive ? "bg-blue-50 text-blue-900 font-semibold dark:bg-slate-800 dark:text-white" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`}>{label}</NavLink>
        ))}
      </aside>
      <div className="flex-1 min-w-0">
        <header className="flex items-center gap-3 px-4 py-2 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm">
          <span className="px-2 py-0.5 rounded bg-slate-800 text-white text-xs font-mono" title={JSON.stringify(health.providers || {})}>{health.mode || "…"} mode</span>
          <span className="text-xs text-slate-500 hidden sm:inline">Store: {health.store} · Object Detector: {health.object_detector}</span>
          <div className="flex-1" />
          <button className="btn2" onClick={() => setDark(!dark)}>{dark ? "Light" : "Dark"}</button>
          <span className="text-xs">{user.sub} · {user.role}{user.region !== "ALL" ? ` (${user.region})` : ""}</span>
          <button className="btn2" onClick={async () => { await api("/auth/logout", { method: "POST" }); setUser(null); }}>Sign out</button>
        </header>
        <main className="p-4">
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
    <Ctx.Provider value={{ user, setUser }}>
      <BrowserRouter>{user ? <Shell /> : <Login onDone={load} />}</BrowserRouter>
    </Ctx.Provider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<Root />);
