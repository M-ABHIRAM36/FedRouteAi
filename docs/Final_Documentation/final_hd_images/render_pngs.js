/* Generate per-figure HTML (svg sized in px) + a manifest for headless rasterization.
   Usage: node render_pngs.js [srcDir]
   Then a headless Chromium/Edge screenshots each HTML at 3x into ./png/. */
"use strict";
const fs = require("fs");
const path = require("path");
const { FIGS, DEFS } = require("./app.js");
const FONT = "'Segoe UI','Inter',system-ui,Arial,sans-serif";
const srcDir = process.argv[2] || path.join(__dirname, "_png_src");
const pngDir = path.join(__dirname, "png");
fs.mkdirSync(srcDir, { recursive: true });
fs.mkdirSync(pngDir, { recursive: true });
const clean = s => s.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "");
const man = [];
for (const f of FIGS) {
  const key = f.num.replace(".", "_");
  const { w, h, body } = f.build();
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" font-family="${FONT}"><rect x="0" y="0" width="${w}" height="${h}" fill="#ffffff"/>${DEFS}${body}</svg>`;
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>*{margin:0;padding:0}svg{display:block}</style></head><body>${svg}</body></html>`;
  const hp = path.join(srcDir, key + ".html");
  fs.writeFileSync(hp, html, "utf8");
  man.push({ num: f.num, key, w, h, html: hp, png: path.join(pngDir, `Fig_${f.num}_${clean(f.name)}.png`) });
}
fs.writeFileSync(path.join(srcDir, "manifest.json"), JSON.stringify(man, null, 1));
console.log("wrote " + man.length + " html files + manifest to " + srcDir);
