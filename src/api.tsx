export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const init: RequestInit = { credentials: "include", ...opts };
  if (opts.json !== undefined) {
    init.method = init.method || "POST";
    init.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    init.body = JSON.stringify(opts.json);
  }
  const r = await fetch("/api" + path, init);
  const ct = r.headers.get("content-type") || "";
  const body = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw Object.assign(new Error((body && body.detail) || r.statusText), { status: r.status, body });
  return body as T;
}

export const SEV: Record<string, string> = {
  HIGH: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  MEDIUM: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  LOW: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300",
  INFO: "bg-slate-100 text-slate-700",
};

export const VSTAT: Record<string, string> = {
  VERIFIED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  MISMATCH: "bg-red-100 text-red-800", SIGNATURE_INVALID: "bg-red-100 text-red-800",
  NOT_FOUND: "bg-amber-100 text-amber-800", SOURCE_UNAVAILABLE: "bg-amber-100 text-amber-800",
  MANUAL_REVIEW: "bg-slate-200 text-slate-700", EXPIRED: "bg-red-100 text-red-800",
};

export function Chip({ text, cls }: { text: string; cls?: string }) {
  return <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-semibold ${cls || "bg-slate-100 text-slate-700"}`}>{text}</span>;
}
