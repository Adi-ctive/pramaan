import { BadgeCheck, Building2, Camera, CheckCheck, FileCheck2, Files, Ruler, ScanEye, ScanText, Users } from "lucide-react";
import { useEffect, useLayoutEffect, useState } from "react";

export const CHECK_ICON: Record<string, any> = {
  complete: Files, valid: FileCheck2, names: Users, records: Building2, tamper: ScanEye, issuer: BadgeCheck, photos: Camera,
  infra: Ruler, read: ScanText, ok: CheckCheck,
};

type Step = { sel: string; text: string };

function seen(id: string) {
  try { return localStorage.getItem("tour:off") === "1" || localStorage.getItem(`tour:${id}`) === "1"; } catch { return true; }
}

/** Click-through tour: dims the page, spotlights one element at a time with a short explanation.
 *  Shows once per page on first visit; the "Show me around" button replays it. */
export function Tour({ id, steps }: { id: string; steps: Step[] }) {
  const [i, setI] = useState<number | null>(null);
  const [box, setBox] = useState<DOMRect | null>(null);
  useEffect(() => {
    const t = setTimeout(() => { if (!seen(id)) setI(0); }, 600);
    const replay = () => setI(0);
    window.addEventListener("pramaan:tour", replay);
    return () => { clearTimeout(t); window.removeEventListener("pramaan:tour", replay); };
  }, [id]);
  useLayoutEffect(() => {
    if (i === null) return;
    const el = document.querySelector(steps[i].sel) as HTMLElement | null;
    if (!el) { setBox(null); return; }
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    const upd = () => setBox(el.getBoundingClientRect());
    const t = setTimeout(upd, 350);
    window.addEventListener("resize", upd);
    window.addEventListener("scroll", upd, true);
    return () => { clearTimeout(t); window.removeEventListener("resize", upd); window.removeEventListener("scroll", upd, true); };
  }, [i]);
  if (i === null) return null;
  const done = () => { try { localStorage.setItem(`tour:${id}`, "1"); } catch {} setI(null); };
  const pad = 8;
  const below = box ? box.bottom + 180 < window.innerHeight : true;
  const tipTop = box ? (below ? box.bottom + pad + 10 : Math.max(10, box.top - pad - 170)) : window.innerHeight / 2 - 80;
  const tipLeft = box ? Math.min(Math.max(10, box.left), window.innerWidth - 340) : window.innerWidth / 2 - 165;
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-label="Guided tour">
      {box ? (
        <div className="absolute rounded-xl transition-all duration-300 pointer-events-none"
          style={{ left: box.left - pad, top: box.top - pad, width: box.width + 2 * pad, height: box.height + 2 * pad, boxShadow: "0 0 0 9999px rgba(15,23,42,.6)", outline: "3px solid #fb923c" }} />
      ) : <div className="absolute inset-0 bg-slate-900/60" />}
      <div className="absolute w-[330px] rounded-xl bg-white dark:bg-slate-900 shadow-2xl p-4 transition-all duration-300" style={{ top: tipTop, left: tipLeft }}>
        <div className="text-xs font-semibold text-orange-600">Step {i + 1} of {steps.length}</div>
        <div className="mt-1 text-[15px] leading-snug">{steps[i].text}</div>
        <div className="flex items-center gap-2 mt-3">
          <button className="text-xs text-slate-500 hover:underline" onClick={done}>Skip tour</button>
          <div className="flex-1" />
          {i > 0 && <button className="btn2" onClick={() => setI(i - 1)}>Back</button>}
          <button className="btn" onClick={() => (i < steps.length - 1 ? setI(i + 1) : done())}>{i < steps.length - 1 ? "Next" : "Got it"}</button>
        </div>
      </div>
    </div>
  );
}
