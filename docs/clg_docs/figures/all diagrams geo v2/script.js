// FedRouteAI Paper Diagrams — shared behavior across all pages

(function themeInit() {
  const saved = localStorage.getItem('fra-theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);
})();

function toggleTheme() {
  const root = document.documentElement;
  const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  if (next === 'dark') root.setAttribute('data-theme', 'dark');
  else root.removeAttribute('data-theme');
  localStorage.setItem('fra-theme', next);
}

/**
 * Downloads the page's main diagram <svg> as a standalone, self-contained
 * .svg file — safe to open directly in Inkscape/Illustrator or convert to
 * PDF/EPS for LaTeX (e.g. `inkscape figure.svg --export-type=pdf`).
 * Each diagram embeds its own <style> block internally (see each page's
 * inline <svg><defs><style>...), so no external stylesheet is needed for
 * the exported file to render correctly standalone.
 */
function downloadSVG(svgId, filename) {
  const svg = document.getElementById(svgId);
  if (!svg) { console.error('SVG not found:', svgId); return; }

  const clone = svg.cloneNode(true);
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clone.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');

  const serializer = new XMLSerializer();
  let source = serializer.serializeToString(clone);
  if (!source.match(/^<\?xml/)) {
    source = '<?xml version="1.0" standalone="no"?>\r\n' + source;
  }

  const blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || 'figure.svg';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Render KaTeX on any element with class="tex" after DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  if (window.renderMathInElement) {
    renderMathInElement(document.body, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false }
      ],
      throwOnError: false
    });
  }
});
