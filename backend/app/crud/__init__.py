"""
CRUD package for database entities.
"""
from backend.app.crud.crud_knowledge_base import (
    get_all_knowledge_bases,
    get_courses_for_ui,
    get_knowledge_base_by_id,
)

__all__ = [
    "get_all_knowledge_bases",
    "get_courses_for_ui",
    "get_knowledge_base_by_id",
]
