import os
import re
import subprocess
from PIL import Image

def render_standalone_figures():
    diagrams_dir = r"C:\Users\DELL\Desktop\Major Project\fedrouteai\docs\paper-diagrams all\paper-diagrams"
    figures_output_dir = r"C:\Users\DELL\Desktop\Major Project\fedrouteai\docs\paper\final_compilable_project\figures"
    temp_dir = r"C:\Users\DELL\Desktop\Major Project\fedrouteai\scratch"
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(figures_output_dir, exist_ok=True)

    fig_mapping = [
        ("architecture.html", "fig1-svg", "fig1_system_architecture.png", 1400, 900),
        ("historical_memory.html", "fig2-svg", "fig2_historical_memory.png", 1360, 820),
        ("feature_engineering.html", "fig3-svg", "fig3_feature_engineering.png", 1360, 780),
        ("ood_pipeline.html", "fig4-svg", "fig4_ood_pipeline.png", 1360, 860),
        ("adaptivefedavg.html", "fig5-svg", "fig5_adaptivefedavg.png", 1360, 860),
        ("communication.html", "fig6-svg", "fig6_fl_communication.png", 1360, 720),
    ]

    edge_binary = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    for html_file, svg_id, out_name, width, height in fig_mapping:
        src_path = os.path.join(diagrams_dir, html_file)
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()

        svg_match = re.search(f'(<svg id="{svg_id}".*?</svg>)', content, re.DOTALL)
        if not svg_match:
            print(f"Error: could not find SVG {svg_id} in {html_file}")
            continue

        svg_str = svg_match.group(1)

        # Scale window for higher DPI (e.g. 2x)
        scale = 2
        win_w = width * scale
        win_h = height * scale

        standalone_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ width: {win_w}px; height: {win_h}px; background: #ffffff; overflow: hidden; }}
  svg {{ display: block; width: {win_w}px; height: {win_h}px; }}
</style>
</head>
<body>
{svg_str}
</body>
</html>"""

        temp_html_path = os.path.join(temp_dir, f"render_{svg_id}.html")
        out_png_path = os.path.join(figures_output_dir, out_name)

        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(standalone_html)

        cmd = [
            edge_binary,
            "--headless",
            "--disable-gpu",
            f"--window-size={win_w},{win_h}",
            f"--screenshot={out_png_path}",
            f"file:///{temp_html_path.replace(os.sep, '/')}"
        ]

        print(f"Rendering {out_name} at {win_w}x{win_h}...")
        subprocess.run(cmd, check=True)

        # Crop transparent / white bounding box edges if needed
        if os.path.exists(out_png_path):
            img = Image.open(out_png_path)
            # Verify non-empty
            print(f"  -> Generated {out_name}: size={img.size}")

if __name__ == "__main__":
    render_standalone_figures()
