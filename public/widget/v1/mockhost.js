/* Shared script for the two mock host portals. The host's own back-end (/api/mock-hosts/{h}/start) holds its API key. */
function mockHost(h, opts) {
  var $ = function (id) { return document.getElementById(id); };
  fetch("/api/mock-hosts/" + h + "/institutions").then(function (r) { return r.json(); }).then(function (list) {
    $("inst").innerHTML = list.map(function (i) {
      return '<option value="' + i.id + '"' + (i.id === opts.defaultInst ? " selected" : "") + ">" + i.id + " - " + i.name + "</option>";
    }).join("");
  });
  var appId = null, ref = null, saved = null;
  try { saved = JSON.parse(sessionStorage.getItem("pramaan-" + h) || "null"); } catch (e) { saved = null; }
  function show(step) { document.querySelectorAll("[data-step]").forEach(function (s) { s.hidden = s.dataset.step !== String(step); }); }
  function poll() {
    if (!appId) return;
    fetch("/api/mock-hosts/" + h + "/inbox?app_id=" + appId).then(function (r) { return r.json(); }).then(function (rows) {
      $("status").innerHTML = rows.length ? rows.map(function (x) {
        return "<li>" + x.ts.slice(11, 19) + " - <b>" + x.payload.event + "</b> (report v" + x.payload.report_version + ") signature " + (x.signature_ok ? "verified" : "BAD") + "</li>";
      }).join("") : "<li>No webhook received yet.</li>";
    });
  }
  function startWidget(tok) {
    window.Pramaan.mount($("pramaan-uploader"), { session: tok, lang: "en" });
    $("pramaan-uploader").addEventListener("pramaan:deficiencies", poll);
    poll();
  }
  $("start").onclick = function () {
    ref = (h === "a" ? "APR-" : "UNI-") + Math.floor(Math.random() * 90000 + 10000);
    $("start").disabled = true;
    fetch("/api/mock-hosts/" + h + "/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ institution_id: $("inst").value, external_ref: ref, form: opts.form() })
    }).then(function (r) { return r.json(); }).then(function (j) {
      appId = j.application_id;
      try { sessionStorage.setItem("pramaan-" + h, JSON.stringify({ appId: appId, tok: j.token, ref: ref })); } catch (e) {}
      $("ref").textContent = ref;
      show(opts.docStep);
      startWidget(j.token);
    });
  };
  $("reset").onclick = function () { try { sessionStorage.removeItem("pramaan-" + h); } catch (e) {} location.reload(); };
  if (saved) { appId = saved.appId; ref = saved.ref; $("ref").textContent = ref; show(opts.docStep); startWidget(saved.tok); }
  setInterval(poll, 5000);
  return { show: show };
}
