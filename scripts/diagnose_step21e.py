"""
Read-only Step 21E database diagnostic.

Prints the minimum non-secret state required to distinguish application bugs
from missing development/test data. No passwords, session tokens, or secrets
are printed and no database rows are modified.
"""

from sqlalchemy import func, select

from backend.app.core.config import settings
from backend.app.db.session import get_db_session
from backend.app.models.document import Document, DocumentChunk
from backend.app.models.indexing_job import IndexingJob
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseMember
from backend.app.models.user import User


def main() -> None:
    print("STEP 21E DATABASE DIAGNOSTIC (READ ONLY)")
    print(f"Database target: {settings.DATABASE_URL.rsplit('@', 1)[-1]}")
    print()

    with get_db_session() as db:
        users = db.execute(select(User).order_by(User.created_at.asc())).scalars().all()
        courses = (
            db.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at.asc()))
            .scalars()
            .all()
        )
        members = (
            db.execute(select(KnowledgeBaseMember).order_by(KnowledgeBaseMember.granted_at.asc()))
            .scalars()
            .all()
        )
        documents = db.execute(select(Document).order_by(Document.created_at.asc())).scalars().all()

        chunk_count = db.execute(select(func.count(DocumentChunk.id))).scalar_one()
        embedding_count = db.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.embedding.is_not(None))
        ).scalar_one()
        jobs = (
            db.execute(select(IndexingJob).order_by(IndexingJob.created_at.desc())).scalars().all()
        )

        print("USERS")
        for user in users:
            print(
                f"- {user.email} | role={user.role} | admin_role={user.admin_role} "
                f"| active={user.is_active} | permissions={user.permissions or []}"
            )

        print("\nCOURSES")
        for course in courses:
            print(f"- {course.name} | id={course.id} | created_by={course.created_by_id}")

        print("\nCOURSE MEMBERSHIPS")
        if members:
            for member in members:
                print(
                    f"- course={member.knowledge_base_id} | user={member.user_id} "
                    f"| granted_at={member.granted_at}"
                )
        else:
            print("- none")

        print("\nDOCUMENTS")
        for document in documents:
            print(
                f"- {document.original_filename} | course={document.knowledge_base_id} "
                f"| status={document.status} | indexing={document.indexing_status} "
                f"| active={document.is_active} | indexed_at={document.indexed_at}"
            )

        print("\nVECTOR COUNTS")
        print(f"- document_chunks: {chunk_count}")
        print(f"- chunks_with_embeddings: {embedding_count}")

        print("\nINDEXING JOBS")
        if jobs:
            for job in jobs:
                print(
                    f"- document={job.document_id} | status={job.status} | stage={job.stage} "
                    f"| total={job.total_chunks} | processed={job.processed_chunks} "
                    f"| embedded={job.embedded_chunks} | indexed={job.indexed_chunks} "
                    f"| attempt={job.attempt_number}"
                )
        else:
            print("- none")


if __name__ == "__main__":
    main()
