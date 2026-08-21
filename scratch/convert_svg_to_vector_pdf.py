import os
import re
import subprocess
import fitz  # PyMuPDF

def generate_vector_pdfs():
    diagrams_dir = r"C:\Users\DELL\Desktop\Major Project\fedrouteai\docs\paper-diagrams all\paper-diagrams"
    figures_output_dir = r"C:\Users\DELL\Desktop\Major Project\fedrouteai\docs\paper\final_compilable_project\figures"
    temp_dir = r"C:\Users\DELL\Desktop\Major Project\fedrouteai\scratch"

    os.makedirs(figures_output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    fig_mapping = [
        ("architecture.html", "fig1-svg", "fig1_system_architecture", 1400, 900),
        ("historical_memory.html", "fig2-svg", "fig2_historical_memory", 1360, 820),
        ("feature_engineering.html", "fig3-svg", "fig3_feature_engineering", 1360, 780),
        ("ood_pipeline.html", "fig4-svg", "fig4_ood_pipeline", 1360, 860),
        ("adaptivefedavg.html", "fig5-svg", "fig5_adaptivefedavg", 1360, 860),
        ("communication.html", "fig6-svg", "fig6_fl_communication", 1360, 720),
    ]

    edge_binary = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    for html_file, svg_id, base_name, width, height in fig_mapping:
        src_path = os.path.join(diagrams_dir, html_file)
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()

        svg_match = re.search(f'(<svg id="{svg_id}".*?</svg>)', content, re.DOTALL)
        if not svg_match:
            print(f"Error: could not find SVG {svg_id} in {html_file}")
            continue

        svg_str = svg_match.group(1)

        # 1. Save standalone SVG file in figures/
        svg_out_path = os.path.join(figures_output_dir, f"{base_name}.svg")
        svg_file_content = f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n{svg_str}'
        with open(svg_out_path, "w", encoding="utf-8") as f:
            f.write(svg_file_content)
        print(f"Saved SVG: {base_name}.svg")

        # 2. Create standalone HTML for PDF printing
        temp_html_path = os.path.join(temp_dir, f"render_{base_name}.html")
        final_vector_pdf = os.path.join(figures_output_dir, f"{base_name}.pdf")

        # Set @page to match pixel dimensions in points (1px = 0.75pt in PDF)
        pt_w = width * 0.75
        pt_h = height * 0.75

        page_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  @page {{ size: {pt_w}pt {pt_h}pt; margin: 0; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ width: {width}px; height: {height}px; background: #ffffff; overflow: hidden; }}
  svg {{ display: block; width: {width}px; height: {height}px; }}
</style>
</head>
<body>
{svg_str}
</body>
</html>"""

        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(page_html)

        cmd = [
            edge_binary,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={final_vector_pdf}",
            f"file:///{temp_html_path.replace(os.sep, '/')}"
        ]

        subprocess.run(cmd, check=True)

        if os.path.exists(final_vector_pdf):
            print(f"  -> Generated Vector PDF: {base_name}.pdf (size: {os.path.getsize(final_vector_pdf)} bytes)")

if __name__ == "__main__":
    generate_vector_pdfs()
