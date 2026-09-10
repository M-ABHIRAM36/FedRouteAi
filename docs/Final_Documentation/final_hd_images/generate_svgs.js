/* Pre-generate all 22 figures as standalone .svg files (vector, print-ready).
   Run:  node generate_svgs.js      (from this folder)
   Output: ./svg/Fig_<num>_<name>.svg
   PNG export is available from index.html (browser) via the PNG buttons. */
"use strict";
const fs = require("fs");
const path = require("path");
const { FIGS, wrap } = require("./app.js");

const outDir = path.join(__dirname, "svg");
fs.mkdirSync(outDir, { recursive: true });

const clean = s => s.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "");
let n = 0;
for (const f of FIGS) {
  const key = f.num.replace(".", "_");
  const { w, h, body } = f.build();
  const svg = '<?xml version="1.0" encoding="UTF-8"?>\n' + wrap(key, w, h, body);
  const name = `Fig_${f.num}_${clean(f.name)}.svg`;
  fs.writeFileSync(path.join(outDir, name), svg, "utf8");
  n++;
  console.log("  " + name);
}
console.log(`\nwrote ${n} SVG files to ${outDir}`);
