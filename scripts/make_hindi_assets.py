"""Renders Hindi/bilingual synthetic documents through Chromium (correct Devanagari shaping) so the seed can use them
on any platform. Writes pramaan/assets/*.pdf. Run once after changing the templates: python scripts/make_hindi_assets.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CSS = """@page{margin:0}body{font-family:'Nirmala UI','Noto Sans Devanagari',sans-serif;margin:0;padding:48px;color:#111}h1{font-size:22px}
.hdr{background:#1f3866;color:#fff;padding:14px 18px;margin:-48px -48px 24px}.hdr b{font-size:18px}.hdr small{display:block;font-size:11px}
p{font-size:15px;line-height:1.7;margin:6px 0}.seal{position:absolute;right:90px;bottom:120px;width:110px;height:110px;border:3px solid #3350b0;
border-radius:50%;color:#3350b0;font-size:11px;display:flex;align-items:center;justify-content:center;text-align:center}
.sig{position:absolute;left:60px;bottom:120px;font-family:'Segoe Script',cursive;font-size:22px}.sigl{position:absolute;left:60px;bottom:96px;font-size:12px}"""


def affidavit_html(deponent, society, date, values_hindi=False):
    return f"""<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="hdr"><b>नोटरी पब्लिक (मॉक) / Notary Public (mock)</b><small>Fictional, for prototype testing. Not a government document.</small></div>
<h1>शपथ पत्र / General Affidavit</h1>
<p>मैं, शपथकर्ता, सत्यनिष्ठा से प्रतिज्ञान करता/करती हूँ कि आवेदन में दी गई जानकारी सत्य है।</p>
<p>I solemnly affirm that the information furnished is true (illustrative).</p>
<p>शपथकर्ता: {deponent}</p><p>संस्था का नाम: {society}</p><p>दिनांक: {date}</p>
<div class="seal">(mock seal)<br>नोटरी</div><div class="sig">{'हस्ताक्षर' if values_hindi else 'A. Signatory'}</div><div class="sigl">Authorised signatory</div>
</body></html>"""


def render(html, out_pdf=None, out_png=None):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1240, "height": 1754})
        pg.set_content(html)
        data = pg.pdf(format="A4", print_background=True) if out_pdf is not None else None
        img = pg.screenshot(full_page=False) if out_png is not None else None
        b.close()
    if out_pdf:
        open(out_pdf, "wb").write(data)
    return data, img


if __name__ == "__main__":
    os.makedirs(os.path.join(ROOT, "pramaan", "assets"), exist_ok=True)
    out = os.path.join(ROOT, "pramaan", "assets", "affidavit_hi_GOLDEN-A.pdf")
    render(affidavit_html("A. Fictional Secretary", "Shivalik Education Society", "02-10-2026"), out_pdf=out)
    print("wrote", out)
