/* PRAMAAN upload widget v1. Framework-free, Shadow DOM. Embed:
   <div id="pramaan-uploader"></div>
   <script src="/widget/v1/pramaan.js" data-session="TOKEN" data-lang="en"></script>
   or call Pramaan.mount(element, {session, lang}) after creating an upload session server-side. */
(function () {
  var T = {
    en: { title: "Documents", required: "required", optional: "optional", choose: "Choose file", submit: "Submit for validation", checking: "Checking...",
      submitted: "Submitted. Validation report received.", defs: "Items to fix", none: "No items to fix. The authority will now review your application.",
      reup: "Re-upload", auth: "Some documents need verification by the authority.", lab: "Facility", lang: "हिन्दी", busy: "Validating, please wait..." },
    hi: { title: "दस्तावेज़", required: "आवश्यक", optional: "वैकल्पिक", choose: "फ़ाइल चुनें", submit: "सत्यापन के लिए जमा करें", checking: "जाँच हो रही है...",
      submitted: "जमा हो गया। सत्यापन रिपोर्ट मिली।", defs: "सुधार हेतु बिंदु", none: "सुधार हेतु कोई बिंदु नहीं। प्राधिकरण अब आवेदन की समीक्षा करेगा।",
      reup: "फिर से अपलोड करें", auth: "कुछ दस्तावेज़ों का प्राधिकरण द्वारा सत्यापन आवश्यक है।", lab: "सुविधा", lang: "English", busy: "सत्यापन हो रहा है, कृपया प्रतीक्षा करें..." }
  };
  var CSS = ":host{all:initial;font-family:system-ui,sans-serif;color:#0f172a;--pramaan-primary:#1e3a8a}" +
    ".w{border:1px solid #cbd5e1;border-radius:10px;padding:14px;background:#fff}.h{display:flex;align-items:center;gap:8px;margin-bottom:8px}" +
    ".h b{flex:1;font-size:15px}.slot{border-top:1px solid #e2e8f0;padding:8px 0}.lbl{font-size:13px;font-weight:600}.req{font-size:11px;color:#64748b;margin-left:6px}" +
    ".row{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:4px}input[type=file]{font-size:12px;max-width:100%}select{font-size:12px}" +
    ".res{font-size:12px;margin-top:4px}.ok{color:#047857}.warn{color:#b45309}.error{color:#b91c1c}.files{font-size:11px;color:#475569}" +
    "button{font:inherit;font-size:13px;border-radius:6px;border:1px solid #94a3b8;background:#fff;padding:5px 10px;cursor:pointer}" +
    "button.p{background:var(--pramaan-primary);color:#fff;border-color:var(--pramaan-primary)}button:disabled{opacity:.5}" +
    ".def{margin-top:10px;border:1px solid #fcd34d;background:#fffbeb;border-radius:8px;padding:10px;font-size:13px}.def li{margin:4px 0}.foot{font-size:10px;color:#94a3b8;margin-top:8px}";

  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) { if (attrs[k] === null || attrs[k] === undefined) continue; if (k === "text") e.textContent = attrs[k]; else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), attrs[k]); else e.setAttribute(k, attrs[k]); }
    (kids || []).forEach(function (c) { if (c) e.appendChild(c); });
    return e;
  }

  function mount(host, opts) {
    var base = opts.base || "", tok = opts.session, lang = opts.lang || "en";
    var root = host.shadowRoot || host.attachShadow({ mode: "open" });
    var state = { s: null, results: {}, defs: null, busy: false };
    function call(path, init) {
      init = init || {};
      init.headers = Object.assign({ "X-Session": tok }, init.headers || {});
      return fetch(base + "/api/widget/" + path, init).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); });
    }
    function emit(name, detail) { host.dispatchEvent(new CustomEvent(name, { detail: detail, bubbles: true, composed: true })); }
    function upload(slot, file, facility) {
      var fd = new FormData();
      fd.append("slot", slot.slot);
      fd.append("file", file);
      if (facility) fd.append("facility", facility);
      state.results[slot.slot] = { level: "", text: T[lang].checking };
      render();
      return call("upload", { method: "POST", body: fd }).then(function (r) {
        state.results[slot.slot] = r.j.detail ? { level: "error", text: String(r.j.detail) } : r.j;
        emit("pramaan:file-checked", { slot: slot.slot, result: r.j });
        return load().then(function () { if (r.j.rerun) return defs(); });
      });
    }
    function defs() {
      return call("deficiencies").then(function (r) { state.defs = r.j; emit("pramaan:deficiencies", r.j); render(); });
    }
    function load() { return call("session").then(function (r) { state.s = r.j; render(); }); }
    function submit() {
      state.busy = true; render();
      emit("pramaan:ready-to-submit", { application_id: state.s.application_id });
      call("submit", { method: "POST" }).then(function () { state.busy = false; return load().then(defs); });
    }
    function render() {
      var t = T[lang], s = state.s;
      root.innerHTML = "";
      root.appendChild(el("style", { text: CSS }));
      if (!s) { root.appendChild(el("div", { class: "w", text: s === null ? "..." : "Session expired" })); return; }
      var w = el("div", { class: "w" }, [el("div", { class: "h" }, [el("b", { text: t.title + " - " + s.host }),
        el("button", { text: t.lang, onclick: function () { lang = lang === "en" ? "hi" : "en"; render(); } })])]);
      s.slots.forEach(function (sl) {
        var fac = null, row = el("div", { class: "row" });
        if (sl.multiple && s.facilities.length) {
          fac = el("select", {}, s.facilities.map(function (f) { return el("option", { value: f.id, text: t.lab + ": " + f.id }); }));
          row.appendChild(fac);
        }
        row.appendChild(el("input", { type: "file", accept: sl.accept, "aria-label": sl.label, onchange: function (e) {
          var fs = Array.prototype.slice.call(e.target.files);
          fs.reduce(function (p, f) { return p.then(function () { return upload(sl, f, fac && fac.value); }); }, Promise.resolve());
        } }));
        if (sl.multiple) row.lastChild.setAttribute("multiple", "");
        var res = state.results[sl.slot];
        w.appendChild(el("div", { class: "slot" }, [
          el("div", {}, [el("span", { class: "lbl", text: sl.label }), el("span", { class: "req", text: sl.required ? t.required : t.optional })]),
          sl.files.length ? el("div", { class: "files", text: "✓ " + sl.files.join(", ") }) : null, row,
          res ? el("div", { class: "res " + res.level, text: (res.level === "ok" ? "✓ " : res.level === "error" ? "✗ " : res.level ? "⚠ " : "") + res.text }) : null]));
      });
      if (s.status === "DRAFT") w.appendChild(el("div", { class: "row" }, [el("button", { class: "p", text: state.busy ? t.busy : t.submit, disabled: state.busy ? "" : null, onclick: submit })]));
      if (state.busy && s.status !== "DRAFT") w.appendChild(el("div", { class: "res", text: t.busy }));
      if (state.defs && s.status !== "DRAFT") {
        var d = state.defs, box = el("div", { class: "def" }, [el("b", { text: d.items.length ? t.defs : t.submitted })]);
        if (!d.items.length) box.appendChild(el("div", { text: t.none }));
        var ul = el("ul");
        d.items.forEach(function (i) { ul.appendChild(el("li", { text: i.title + " - " + i.action })); });
        box.appendChild(ul);
        if (d.pending_authority_verification) box.appendChild(el("div", { text: "• " + t.auth }));
        box.appendChild(el("div", { class: "foot", text: "Use the file buttons above to " + t.reup.toLowerCase() + ". Only the affected checks re-run." }));
        w.appendChild(box);
      }
      w.appendChild(el("div", { class: "foot", text: "Powered by PRAMAAN validation engine (prototype). Findings are advisory." }));
      root.appendChild(w);
    }
    load().then(function () { if (state.s && state.s.status !== "DRAFT") defs(); });
    return { reload: load };
  }

  window.Pramaan = { mount: mount };
  var me = document.currentScript;
  if (me && me.dataset.session) {
    var target = document.getElementById("pramaan-uploader");
    if (target) mount(target, { session: me.dataset.session, lang: me.dataset.lang });
  }
})();
