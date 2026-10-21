"""site/heat.js must size rooms and label miner fits exactly like heat_need / heat_fit / heat_rank in build_site.py."""
import ast
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = {"HEAT_WPSF", "heat_need", "heat_fit", "heat_rank"}


def py_funcs():
    """Load just the heat helpers from build_site.py (importing it would build the whole site)."""
    tree = ast.parse((ROOT / "build_site.py").read_text())
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in NAMES)
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in NAMES for t in n.targets))]
    ns = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "build_site_heat", "exec"), ns)
    return ns


SIZES = [1, 50, 100, 120, 150, 200, 250, 300, 400, 600, 1000, 2500]
WATTS = [25, 100, 140, 300, 330, 400, 800, 860, 1500, 1674]
INS = ["good", "average", "poor", "unknown"]

JS = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(%s, 'utf8'));
const H = window.RadarHeat, inp = JSON.parse(fs.readFileSync(0, 'utf8')), out = [];
for (const s of inp.sizes) for (const i of inp.ins) { const n = H.need(s, i); for (const w of inp.watts) out.push([n, H.fit(w, n), H.rank(w, n)]); }
process.stdout.write(JSON.stringify(out));
"""


class HeatCalc(unittest.TestCase):
    def test_rule_of_thumb(self):
        f = py_funcs()
        self.assertEqual(f["heat_need"](150), 1500)
        self.assertEqual(f["heat_fit"](1500, 1500), "fits")
        self.assertEqual(f["heat_fit"](800, 1500), "helps")
        self.assertEqual(f["heat_fit"](140, 1500), "small")
        self.assertEqual(f["heat_fit"](1674, 700), "big")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_js_matches_python(self):
        f = py_funcs()
        want = []
        for s in SIZES:
            for i in INS:
                n = f["heat_need"](s, i)
                for w in WATTS:
                    want.append([n, f["heat_fit"](w, n), f["heat_rank"](w, n)])
        got = json.loads(subprocess.run(["node", "-e", JS % json.dumps(str(ROOT / "site" / "heat.js"))],
                                        input=json.dumps({"sizes": SIZES, "ins": INS, "watts": WATTS}),
                                        capture_output=True, text=True, check=True).stdout)
        self.assertEqual(len(got), len(want))
        for g, w in zip(got, want):
            self.assertAlmostEqual(g[0], w[0])
            self.assertEqual(g[1], w[1])
            self.assertAlmostEqual(g[2], w[2])

    def test_page_built(self):
        p = ROOT / "site" / "heat-calculator" / "index.html"
        if not p.exists():
            self.skipTest("run build_site.py first")
        html = p.read_text()
        self.assertIn('id="heat-form"', html)
        self.assertIn('src="/heat.js"', html)
        self.assertIn("data-w=", html)
        self.assertIn("/heat-calculator/", (ROOT / "site" / "sitemap.xml").read_text())
