"""
Audit exact pagination of RAG_Assistant_Project_Report_Draft.pdf using PyMuPDF.
Extracts the exact page number on which each TOC heading, figure caption,
and table caption appears, comparing against front matter.
"""

import os
import fitz

PDF_PATH = os.path.abspath('docs/project-report/RAG_Assistant_Project_Report_Draft.pdf')

doc = fitz.open(PDF_PATH)
total_pages = len(doc)
print(f"Total Pages in Exported PDF: {total_pages}")

# Section 1 has 4 pages: Cover (1), Certificate (2), Company Cert (3), Company Profile (4)
# Section 2 starts at physical page 5: Acknowledgement (5 = Roman v), Abstract (6 = vi), etc.
# Find physical page of CHAPTER 1
chap1_phys_page = None
for i in range(total_pages):
    text = doc[i].get_text()
    if "CHAPTER 1" in text and "INTRODUCTION" in text:
        chap1_phys_page = i + 1
        break

print(f"Chapter 1 starts on physical page: {chap1_phys_page}")
offset = chap1_phys_page - 1  # Arabic page 1 corresponds to physical page chap1_phys_page

print(f"Body Arabic page offset: physical_page - {offset}")

queries = [
    ("Acknowledgements", "ACKNOWLEDGEMENT", "front"),
    ("Abstract", "ABSTRACT", "front"),
    ("List of Figures", "LIST OF FIGURES", "front"),
    ("List of Tables", "LIST OF TABLES", "front"),
    ("Chapter 1    Introduction", "CHAPTER 1", "body"),
    ("    1.1    Overview", "1.1 Overview", "body"),
    ("    1.2    Problem Definition", "1.2 Problem Definition", "body"),
    ("    1.3    Scope/Application", "1.3 Scope/Application", "body"),
    ("Chapter 2    Training Activities", "CHAPTER 2", "body"),
    ("    2.1    Requirements Analysis & Academic Domain Modeling", "2.1 Requirements Analysis", "body"),
    ("    2.2    Framework Selection & System Architecture", "2.2 Framework Selection", "body"),
    ("    2.3    Multi-Format Document Ingestion & Parsers", "2.3 Multi-Format", "body"),
    ("    2.4    Semantic Chunking & Dense Embeddings", "2.4 Semantic Chunking", "body"),
    ("    2.5    Hybrid Retrieval (RRF) & Cross-Encoder Reranking", "2.5 Hybrid Retrieval", "body"),
    ("    2.6    Grounded Prompt Engineering & Local Synthesis", "2.6 Grounded Prompt", "body"),
    ("    2.7    Frontend Rebuild with NiceGUI & Quasar UI", "2.7 Frontend Rebuild", "body"),
    ("    2.8    Security Hardening, Session Management & Reader", "2.8 Security Hardening", "body"),
    ("    2.9    Automated Quality Gates & Test Verification", "2.9 Automated Quality Gates", "body"),
    ("Chapter 3    System Planning", "CHAPTER 3", "body"),
    ("    3.1    Project Development Approach", "3.1 Project Development Approach", "body"),
    ("    3.2    System Modules", "3.2 System Modules", "body"),
    ("        3.2.1    Document Ingestion & Parsing Module", "3.2.1 Document Ingestion", "body"),
    ("        3.2.2    Indexing & Vector Storage Module", "3.2.2 Indexing & Vector", "body"),
    ("        3.2.3    Hybrid Retrieval & Reranking Module", "3.2.3 Hybrid Retrieval", "body"),
    ("        3.2.4    Grounded Generation & Citation Module", "3.2.4 Grounded Generation", "body"),
    ("        3.2.5    Security, Authentication & Access Control Module", "3.2.5 Security, Authentication", "body"),
    ("        3.2.6    User Presentation & Dedicated Reader Module", "3.2.6 User Presentation", "body"),
    ("    3.3    Functional Requirements", "3.3 Functional Requirements", "body"),
    ("    3.4    Non Functional Requirements", "3.4 Non Functional Requirements", "body"),
    ("    3.5    Timeline Chart", "3.5 Timeline Chart", "body"),
    ("Chapter 4    System Design", "CHAPTER 4", "body"),
    ("    4.1    Use Case Diagram", "4.1 Use Case Diagram", "body"),
    ("    4.2    Sequence Diagram", "4.2 Sequence Diagram", "body"),
    ("    4.3    Activity Diagram", "4.3 Activity Diagram", "body"),
    ("    4.4    Class Diagram", "4.4 Class Diagram", "body"),
    ("    4.5    Database Schema", "4.5 Database Schema", "body"),
    ("    4.6    Data Flow Diagram", "4.6 Data Flow Diagram", "body"),
    ("    4.7    ER Diagram", "4.7 ER Diagram", "body"),
    ("Chapter 5    Implementation and Testing", "CHAPTER 5", "body"),
    ("    5.1    Hardware and Software Requirements", "5.1 Hardware and Software Requirements", "body"),
    ("    5.2    Snapshots", "5.2 Snapshots", "body"),
    ("    5.3    Test Cases", "5.3 Test Cases", "body"),
    ("Chapter 6    Conclusion and Future Scope", "CHAPTER 6", "body"),
    ("References", "REFERENCES", "body"),
]

roman_map = {5: "v", 6: "vi", 7: "vii", 8: "viii", 9: "ix", 10: "x", 11: "xi"}

print("\n=== AUDITED TOC ENTRIES ===")
audited_toc = []
for title, needle, kind in queries:
    found_page = None
    start_idx = 4 if kind == "front" else (chap1_phys_page - 1)
    end_idx = (chap1_phys_page - 1) if kind == "front" else total_pages
    for i in range(start_idx, end_idx):
        text = doc[i].get_text()
        if needle.lower() in text.lower():
            if kind == "front":
                found_page = roman_map.get(i + 1, str(i + 1))
            else:
                found_page = str((i + 1) - offset)
            break
    print(f'        ("{title}", "{found_page}", {title.startswith("Chapter ") or title == "References"}, False),')
    audited_toc.append((title, found_page))

figures = [
    ("Figure 3.1", "Figure 3.1:"),
    ("Figure 4.1", "Figure 4.1:"),
    ("Figure 4.2", "Figure 4.2:"),
    ("Figure 4.3", "Figure 4.3:"),
    ("Figure 4.4", "Figure 4.4:"),
    ("Figure 4.5", "Figure 4.5:"),
    ("Figure 4.6", "Figure 4.6:"),
    ("Figure 5.1", "Figure 5.1:"),
    ("Figure 5.2", "Figure 5.2:"),
    ("Figure 5.3", "Figure 5.3:"),
    ("Figure 5.4", "Figure 5.4:"),
    ("Figure 5.5", "Figure 5.5:"),
    ("Figure 5.6", "Figure 5.6:"),
    ("Figure 5.7", "Figure 5.7:"),
    ("Figure 5.8", "Figure 5.8:"),
    ("Figure 5.9", "Figure 5.9:"),
]

print("\n=== AUDITED FIGURE ENTRIES ===")
for fig_id, needle in figures:
    found_page = None
    for i in range(chap1_phys_page - 1, total_pages):
        text = doc[i].get_text()
        if needle.lower() in text.lower():
            found_page = str((i + 1) - offset)
            break
    print(f'        ("{fig_id}", "{found_page}"),')

tables = [
    ("Table 3.1", "Table 3.1:"),
    ("Table 3.2", "Table 3.2:"),
    ("Table 4.1", "Table 4.1:"),
    ("Table 4.2", "Table 4.2:"),
    ("Table 4.3", "Table 4.3:"),
    ("Table 4.4", "Table 4.4:"),
    ("Table 4.5", "Table 4.5:"),
    ("Table 4.6", "Table 4.6:"),
    ("Table 4.7", "Table 4.7:"),
    ("Table 4.8", "Table 4.8:"),
    ("Table 4.9", "Table 4.9:"),
    ("Table 4.10", "Table 4.10:"),
    ("Table 5.1", "Table 5.1:"),
    ("Table 5.2", "Table 5.2:"),
    ("Table 5.3", "Table 5.3:"),
    ("Table 5.4", "Table 5.4:"),
    ("Table 5.5", "Table 5.5:"),
]

print("\n=== AUDITED TABLE ENTRIES ===")
for tbl_id, needle in tables:
    found_page = None
    for i in range(chap1_phys_page - 1, total_pages):
        text = doc[i].get_text()
        if needle.lower() in text.lower():
            found_page = str((i + 1) - offset)
            break
    print(f'        ("{tbl_id}", "{found_page}"),')
