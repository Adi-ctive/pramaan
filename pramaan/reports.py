"""Validation report rendering: HTML (Jinja2) and PDF (ReportLab). Institution view never includes forensic detail."""
import io

from jinja2 import Environment, select_autoescape

TPL = Environment(autoescape=select_autoescape(["html"])).from_string("""<!doctype html><html><head><meta charset="utf-8">
<title>{{ title }} - {{ app.form.institution_name }}</title>
<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#0f172a}h1{margin-bottom:0}
.m{color:#64748b;font-size:13px}table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}td,th{border:1px solid #e2e8f0;padding:4px 6px;text-align:left;vertical-align:top}
.HIGH{color:#b91c1c;font-weight:700}.MEDIUM{color:#b45309;font-weight:700}.LOW{color:#0369a1}.note{font-size:12px;color:#64748b;margin-top:20px}</style></head><body>
<h1>{{ title }}</h1><div class="m">{{ app.form.institution_name }} · {{ app.institution_id }} · {{ app.category }} · via {{ host }} · rule pack {{ pack }}</div>
{% if view == 'institution' %}
<h2>Items to fix</h2>{% if not items %}<p>Nothing to fix.</p>{% endif %}<ol>{% for i in items %}<li><b>{{ i.title }}</b> - {{ i.action }}</li>{% endfor %}</ol>
{% if pending %}<p>Some documents need verification by the authority.</p>{% endif %}
{% else %}
<h2>Summary</h2><p>Report v{{ report.version }} · {{ report.created[:16] }} · {{ report.mode }} mode · {{ report.elapsed_ms }} ms · attention score {{ report.risk }} (sorting aid, not a decision)</p>
{% for s in report.summary %}<p>{{ s.text }} {% for f in s.flags %}[{{ f }}] {% endfor %}</p>{% endfor %}
<h2>Checklist</h2><table><tr><th>Required document</th><th>Status</th></tr>{% for s in required_slots %}<tr><td>{{ taxonomy[s] }}</td>
<td>{% if s in present %}uploaded{% else %}<span class="HIGH">missing</span>{% endif %}</td></tr>{% endfor %}</table>
{% for cat, label in sections %}{% set fs = flags | selectattr('category', 'equalto', cat) | list %}{% if fs %}<h2>{{ label }}</h2><table>
<tr><th>Severity</th><th>Finding</th><th>Expected / observed</th><th>Evidence</th></tr>{% for f in fs %}<tr><td class="{{ f.severity }}">{{ f.severity }}<br>{{ f.status }}</td>
<td><b>{{ f.title }}</b><br>{{ f.reason }}<br><span class="m">{{ f.id }} · {{ f.detector }} · conf {{ f.confidence }}</span></td><td>{{ f.expected or '-' }}<br>{{ f.observed or '-' }}</td>
<td>{% for e in f.evidence %}{{ e.type }}{% if e.key %}: {{ e.key }}{% endif %}{% if e.rule_id %}: {{ e.rule_id }} ({{ e.source_ref }}){% endif %}<br>{% endfor %}</td></tr>{% endfor %}</table>{% endif %}{% endfor %}
<h2>Verification</h2><table><tr><th>Document</th><th>Method</th><th>Source</th><th>Status</th><th>Time</th><th>Digests</th></tr>
{% for v in verifications %}<tr><td>{{ v.doc_id }}</td><td>{{ v.method }}</td><td>{{ v.source }}</td><td>{{ v.status }}</td><td>{{ v.ts[:19] }}</td><td>{{ v.request_digest }} / {{ v.response_digest }}</td></tr>{% endfor %}</table>
<h2>Cases requiring intervention</h2><ul>{% for f in flags if f.severity == 'HIGH' and f.status == 'OPEN' %}<li>{{ f.title }} ({{ f.id }})</li>{% else %}<li>None open.</li>{% endfor %}</ul>
{% endif %}
<p class="note">Decision-support output. Anomaly findings are indicators that require verification. Statutory scrutiny, inspections and final decisions remain with the competent authority.</p>
</body></html>""")

SECTIONS = [("COMPLETENESS", "Completeness"), ("VALIDITY", "Validity"), ("CONSISTENCY", "Consistency findings"), ("ANOMALY", "Anomaly indicators"),
            ("VERIFICATION", "Source verification"), ("INFRASTRUCTURE", "Infrastructure"), ("EXTRACTION", "Manual reading needed")]


def _ctx(d, view):
    if view == "institution":
        return {**d, "view": view}
    present = {x["slot"] for x in d["documents"] if not x.get("superseded")}
    return {**d, "app": d["application"], "view": view, "present": present, "sections": SECTIONS}


def render_html(d, view="full"):
    return TPL.render(**_ctx(d, view))


def render_pdf(d, view="full"):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape as x
    st = getSampleStyleSheet()
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, title=d["title"], leftMargin=36, rightMargin=36)
    a = d["app"] if view == "institution" else d["application"]
    el = [Paragraph(x(d["title"]), st["Title"]),
          Paragraph(x(f"{a['form']['institution_name']} · {a['institution_id']} · {a['category']} · via {d['host']} · {d['pack']}"), st["Normal"]), Spacer(1, 10)]
    if view == "institution":
        el.append(Paragraph("Items to fix", st["Heading2"]))
        for i in d["items"] or [{"title": "Nothing to fix", "action": ""}]:
            el.append(Paragraph(x(f"• {i['title']} - {i['action']}"), st["Normal"]))
        if d["pending"]:
            el.append(Paragraph("• Some documents need verification by the authority.", st["Normal"]))
    else:
        r = d["report"]
        el.append(Paragraph(x(f"Report v{r['version']} · {r['mode']} · {r['elapsed_ms']} ms · attention score {r['risk']} (sorting aid, not a decision)"), st["Normal"]))
        for s in r["summary"]:
            el.append(Paragraph(x(s["text"] + " " + " ".join(f"[{f}]" for f in s["flags"])), st["Normal"]))
        rows = [["Sev", "Finding", "Expected / observed"]]
        for f in d["flags"]:
            rows.append([f["severity"], Paragraph(x(f"{f['title']}. {f['reason']} ({f['id']}, {f['status']})"), st["BodyText"]),
                         Paragraph(x(f"{f.get('expected') or '-'} / {f.get('observed') or '-'}"), st["BodyText"])])
        el += [Spacer(1, 8), Paragraph("Findings", st["Heading2"]), _table(rows, [40, 330, 150])]
        vr = [["Method", "Source", "Status", "Time"]] + [[v["method"], Paragraph(x(str(v["source"])), st["BodyText"]), v["status"], v["ts"][:16]] for v in d["verifications"]]
        el += [Spacer(1, 8), Paragraph("Verification", st["Heading2"]), _table(vr, [70, 250, 110, 90])]
    el += [Spacer(1, 14), Paragraph("Decision-support output. Anomaly findings are indicators that require verification. "
                                    "Final decisions remain with the competent authority.", st["Italic"])]
    doc.build(el)
    return out.getvalue()


def _table(rows, widths):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                           ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t
