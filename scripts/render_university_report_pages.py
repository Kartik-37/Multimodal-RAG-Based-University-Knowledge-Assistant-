"""
Render every page of the final PDF report into high-resolution PNG images
for visual inspection and layout quality assurance.
"""

import os
import pymupdf

REPORT_DIR = os.path.abspath('docs/project-report')
PDF_PATH = os.path.join(REPORT_DIR, 'RAG_Assistant_Project_Report_Draft.pdf')
OUTPUT_DIR = os.path.join(REPORT_DIR, 'rendered_pages')
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"Opening PDF: {PDF_PATH}")
doc = pymupdf.open(PDF_PATH)
total_pages = len(doc)
print(f"Total Pages in Report: {total_pages}")

# Render at 150 DPI for crisp visual inspection
zoom = 150 / 72
mat = pymupdf.Matrix(zoom, zoom)

for page_num in range(total_pages):
    page = doc[page_num]
    pix = page.get_pixmap(matrix=mat)
    out_filename = os.path.join(OUTPUT_DIR, f"page_{page_num + 1:02d}.png")
    pix.save(out_filename)
    text_sample = page.get_text()[:60].replace('\n', ' ')
    print(f"Page {page_num + 1:02d} rendered -> {os.path.basename(out_filename)} ({pix.width}x{pix.height}) | Starts: {text_sample}")

print(f"\nSuccessfully rendered all {total_pages} pages into {OUTPUT_DIR}")
