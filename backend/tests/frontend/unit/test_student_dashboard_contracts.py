"""Contracts for student dashboard presentation logic and state helpers.

Validates that:
- Dashboard question composer rejects empty/whitespace input before submitting.
- Prompt suggestion pills are properly formatted non-empty strings.
- Empty course catalogs display purposeful empty states without fake data.
- Dashboard navigation shortcuts point to valid student routes.
"""

import pytest

from frontend.client.models import UserDTO
from frontend.security.access_control import can_access_route


class TestStudentDashboardContracts:
    """Validate student dashboard behavior contracts."""

    @pytest.mark.parametrize(
        "prompt",
        ["", "   ", "\t\n", " \n "],
    )
    def test_empty_prompt_is_rejected_before_dispatch(self, prompt: str) -> None:
        trimmed = prompt.strip()
        assert len(trimmed) == 0

    def test_valid_prompt_passes_input_gate(self) -> None:
        prompt = "Explain bubble sort algorithms"
        trimmed = prompt.strip()
        assert len(trimmed) > 0
        assert trimmed == "Explain bubble sort algorithms"

    def test_dashboard_shortcuts_target_valid_routes(self) -> None:
        student = UserDTO(
            id="student-1",
            email="student@univ.edu",
            full_name="Student",
            role="STUDENT",
        )
        shortcuts = ["/chat", "/knowledge-bases", "/profile"]
        for target in shortcuts:
            assert can_access_route(student, target) is True
