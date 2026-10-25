"""Inspection aid (not part of the frozen checks): contact sheets of every screenshot of a governed run, and
reduced JPEG copies for the record. usage: python make_sheets.py RESULTS_DIR OUT_DIR"""
import glob, json, os, sys
from PIL import Image, ImageDraw
res, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
TW, TH, COLS, PER = 480, 252, 3, 24
for d in sorted(glob.glob(os.path.join(res, "*", ""))):
    pid = os.path.basename(os.path.dirname(d))
    r = json.load(open(os.path.join(d, "result_offline.json")))
    items = []
    for s in r["snapshots"]:
        for v in s["shots"]:
            items.append(("%02d %s [%s]" % (s["index"], s["name"], v), os.path.join(d, "offline_%02d_%s_%s.png" % (s["index"], s["key"], v))))
    for k in range(0, len(items), PER):
        chunk = items[k:k + PER]
        rows = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * TW, rows * (TH + 18)), "white")
        dr = ImageDraw.Draw(sheet)
        for j, (lab, p) in enumerate(chunk):
            x, y = (j % COLS) * TW, (j // COLS) * (TH + 18)
            im = Image.open(p).convert("RGB").resize((TW, TH), Image.LANCZOS)
            sheet.paste(im, (x, y + 18)); dr.text((x + 4, y + 3), lab, fill="black")
        sheet.save(os.path.join(out, "sheet_%s_%02d.jpg" % (pid, k // PER + 1)), quality=88)
    print(pid, len(items), "screenshots,", (len(items) + PER - 1) // PER, "sheet(s)")
