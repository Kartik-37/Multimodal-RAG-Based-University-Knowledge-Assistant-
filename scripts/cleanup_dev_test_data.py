"""
Safe Development Database Cleanup Script.

Purges historical orphaned test knowledge bases created during early test runs
prior to test database isolation on September 16, 2026.

Safety invariants enforced:
1. Operates ONLY on the configured development database ('rag_assistant_db').
   Explicitly REFUSES to execute against the test database ('rag_assistant_test_db').
2. Default execution is strictly DRY-RUN. Deletion occurs ONLY when '--apply' is passed.
3. Candidate courses must satisfy ALL safety rules:
   - Matches known historical test naming prefix ('Chat Test KB %', 'Doc Test KB %',
     'Test Syllabus %', 'Retrieval DTO KB %').
   - Created on or before September 15, 2026.
   - Has exactly 0 associated documents.
   - Has exactly 0 associated student members.
   - Is NOT in the allowlist of legitimate courses ('Official University Regulations',
     'Computer Architecture', 'BCA').
"""

import argparse
import sys
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import create_engine, func, select

from backend.app.core.config import settings
from backend.app.models.document import Document
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember

PROTECTED_COURSE_NAMES = {
    "official university regulations",
    "computer architecture",
    "bca",
}

HISTORICAL_TEST_PREFIXES = (
    "Chat Test KB",
    "Doc Test KB",
    "Test Syllabus",
    "Retrieval DTO KB",
)


def verify_database_safety(db_url: str) -> None:
    """Verify that connection string targets the development database and NOT the test database."""
    parsed = urlparse(db_url)
    db_name = parsed.path.lstrip("/")

    if "test" in db_name.lower() or "test" in db_url.lower():
        print(f"SAFETY ABORT: Refusing to operate on test database: '{db_name}'.")
        sys.exit(1)

    if db_name != "rag_assistant_db":
        print(f"SAFETY ABORT: Unexpected database target '{db_name}'. Expected 'rag_assistant_db'.")
        sys.exit(1)


def find_cleanup_candidates(session) -> list[KnowledgeBase]:
    """Find knowledge bases that satisfy all safety constraints."""
    cutoff_date = datetime(2026, 9, 16, 0, 0, 0, tzinfo=UTC)

    all_kbs = session.execute(select(KnowledgeBase)).scalars().all()
    candidates: list[KnowledgeBase] = []

    for kb in all_kbs:
        name_lower = kb.name.strip().lower()

        # Rule 1: Never touch protected legitimate courses
        if any(prot in name_lower for prot in PROTECTED_COURSE_NAMES):
            continue

        # Rule 2: Must match recognized historical test prefix
        is_test_prefix = any(kb.name.startswith(pfx) for pfx in HISTORICAL_TEST_PREFIXES)
        if not is_test_prefix:
            continue

        # Rule 3: Must be created prior to test DB isolation (Sep 16, 2026)
        kb_created = kb.created_at
        if kb_created.tzinfo is None:
            kb_created = kb_created.replace(tzinfo=UTC)
        if kb_created >= cutoff_date:
            continue

        # Rule 4: Must have 0 associated documents
        doc_count = (
            session.execute(
                select(func.count(Document.id)).where(Document.knowledge_base_id == kb.id)
            ).scalar()
            or 0
        )
        if doc_count > 0:
            continue

        # Rule 5: Must have 0 associated members
        member_count = (
            session.execute(
                select(func.count(KnowledgeBaseMember.id)).where(
                    KnowledgeBaseMember.knowledge_base_id == kb.id
                )
            ).scalar()
            or 0
        )
        if member_count > 0:
            continue

        candidates.append(kb)

    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safe development database cleanup for historical test knowledge bases."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print candidates without modifying data (default).",
    )
    group.add_argument(
        "--apply",
        action="store_true",
        help="Perform actual deletion of validated test candidates.",
    )

    args = parser.parse_args()
    is_apply = args.apply

    db_url = settings.DATABASE_URL
    print(f"Verifying target database safety: {db_url}")
    verify_database_safety(db_url)

    engine = create_engine(db_url)
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        candidates = find_cleanup_candidates(session)

        print(
            f"\nDiscovered {len(candidates)} candidate test record(s) matching all safety invariants:"
        )
        for c in candidates:
            print(f"  - [{c.id}] '{c.name}' (created: {c.created_at})")

        if not candidates:
            print("\nDatabase is clean. No historical test records found.")
            return

        if not is_apply:
            print(
                "\n[DRY RUN COMPLETE] No records were modified. "
                "To apply this cleanup, run: python scripts/cleanup_dev_test_data.py --apply"
            )
            return

        print(f"\nApplying deletion of {len(candidates)} candidate test record(s)...")
        for c in candidates:
            session.delete(c)
        session.commit()
        print(
            f"Successfully removed {len(candidates)} test knowledge base(s) from development database."
        )


if __name__ == "__main__":
    main()
