"""
Export generated DOCX to PDF via Microsoft Word COM automation.
Also updates fields and pagination.
"""

import os
import sys
import win32com.client

REPORT_DIR = os.path.abspath('docs/project-report')
DOCX_PATH = os.path.join(REPORT_DIR, 'RAG_Assistant_Project_Report_Draft.docx')
PDF_PATH = os.path.join(REPORT_DIR, 'RAG_Assistant_Project_Report_Draft.pdf')

def export_docx_to_pdf():
    print(f"Opening Word COM automation...")
    print(f"Input DOCX: {DOCX_PATH}")
    print(f"Output PDF: {PDF_PATH}")

    word = win32com.client.Dispatch('Word.Application')
    word.Visible = False
    word.DisplayAlerts = False

    try:
        doc = word.Documents.Open(DOCX_PATH)
        print("Document opened successfully.")

        print("Updating document fields...")
        doc.Fields.Update()

        # Update any TOCs
        for toc in doc.TablesOfContents:
            toc.Update()

        for tof in doc.TablesOfFigures:
            tof.Update()

        print(f"Exporting to PDF: {PDF_PATH}...")
        # 17 is wdFormatPDF
        doc.SaveAs(PDF_PATH, FileFormat=17)
        print("PDF export completed.")

        doc.Close(SaveChanges=True)
        print("Document saved and closed.")
    finally:
        word.Quit()
        print("Word application terminated cleanly.")

if __name__ == '__main__':
    export_docx_to_pdf()
