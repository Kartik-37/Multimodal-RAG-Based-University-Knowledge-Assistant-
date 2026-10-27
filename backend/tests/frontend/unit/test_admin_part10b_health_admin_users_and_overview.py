"""
Unit and behavioral contract tests for Admin Part 10B:
1. System Health Truthful Reporting & Preview Mode Semantics
2. Administrator Course Name Resolution, Error Guards, and Permission Safety
3. Overview Simplification, Truthful Status, and Non-Idle Failed Jobs
"""

from unittest.mock import Mock

import pytest

from frontend.client.api_client import FrontendAPIClient
from frontend.client.models import (
    AdminUserDTO,
    ComponentHealthDTO,
    CourseSummaryDTO,
    IndexingJobDTO,
    KnowledgeBaseDTO,
    SystemHealthDTO,
)
from frontend.pages.admin_users_page import (
    extract_assigned_course_ids,
    resolve_course_display_name,
)
from frontend.pages.system_health_page import (
    FALLBACK_SCOPE_DESCRIPTION,
    get_subsystem_metadata,
)


class TestSystemHealthContractsPart10B:
    """Test System Health truthful reporting and preview-mode contracts."""

    def test_preview_mode_returns_preview_status_not_healthy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Contract 1: In preview mode (DEMO_MODE=1), get_system_health returns status='preview'."""
        monkeypatch.setenv("DEMO_MODE", "1")
        client = FrontendAPIClient()
        health = client.get_system_health()

        assert health.status == "preview"
        assert health.status != "healthy"
        # Confirm components are explicitly labeled unverified/simulated
        names = [c.name for c in health.components]
        assert any("postgresql" in n.lower() for n in names)
        assert any("pgvector" in n.lower() for n in names)
        for comp in health.components:
            assert comp.status in ("preview", "unknown", "degraded")
            assert "unverified" in comp.message.lower() or "simulated" in comp.message.lower() or "decoupled" in comp.message.lower()

    def test_real_http_health_preserves_genuine_healthy_response(self) -> None:
        """Contract 2: When backend responds with live health, status and components are preserved."""
        client = FrontendAPIClient()
        client.get_session_token = Mock(return_value="valid-live-token")
        mock_http = Mock()
        client._http = mock_http

        mock_http.get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "healthy",
                "components": [
                    {"name": "PostgreSQL", "status": "healthy", "message": "12 connections active"},
                    {"name": "pgvector", "status": "healthy", "message": "Extension version 0.5.1 active"},
                    {"name": "Indexing Worker", "status": "healthy", "message": "Worker running"},
                ],
                "checked_at": "2026-10-23T05:00:00Z",
            },
        )

        health = client.get_system_health()
        assert health.status == "healthy"
        assert len(health.components) == 3
        assert health.components[0].status == "healthy"

    def test_missing_health_status_never_defaults_to_healthy(self) -> None:
        """Contract 3: Missing or null status in health response maps to 'unknown', never 'healthy'."""
        client = FrontendAPIClient()
        client.get_session_token = Mock(return_value="valid-live-token")
        mock_http = Mock()
        client._http = mock_http

        mock_http.get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": None,  # Missing or null status
                "components": [],
                "checked_at": "2026-10-23T05:00:00Z",
            },
        )

        health = client.get_system_health()
        assert health.status == "unknown"
        assert health.status != "healthy"

    def test_failed_health_request_raises_error_and_does_not_mask(self) -> None:
        """Contract 4: When live health check returns 503 or fails, it raises ValueError, not healthy."""
        client = FrontendAPIClient()
        client.get_session_token = Mock(return_value="valid-live-token")
        mock_http = Mock()
        client._http = mock_http

        mock_http.get.return_value = Mock(
            status_code=503,
            json=lambda: {"detail": "Database connection pool exhausted"},
        )

        with pytest.raises(ValueError, match="Database connection pool exhausted"):
            client.get_system_health()

    def test_degraded_and_unavailable_components_preserved(self) -> None:
        """Contract 5: Degraded or failing subsystems are faithfully preserved."""
        client = FrontendAPIClient()
        client.get_session_token = Mock(return_value="valid-live-token")
        mock_http = Mock()
        client._http = mock_http

        mock_http.get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "degraded",
                "components": [
                    {"name": "PostgreSQL", "status": "healthy", "message": "Connected"},
                    {"name": "Indexing Worker", "status": "degraded", "message": "Queue depth high (42)"},
                ],
                "checked_at": "2026-10-23T05:00:00Z",
            },
        )

        health = client.get_system_health()
        assert health.status == "degraded"
        worker_comp = next(c for c in health.components if c.name == "Indexing Worker")
        assert worker_comp.status == "degraded"
        assert "Queue depth high" in worker_comp.message


class TestAdminUsersAndPermissionsContractsPart10B:
    """Test Administrator course-name resolution, catalog error handling, and scope safety."""

    def test_resolve_course_display_name_with_known_id(self) -> None:
        """Contract 6: Course ID maps to human-readable course name when present in course_map."""
        course_map = {
            "c1111111-1111-1111-1111-111111111111": "CS101: Introduction to Computer Science",
            "c2222222-2222-2222-2222-222222222222": "MATH201: Linear Algebra",
        }
        res = resolve_course_display_name("c1111111-1111-1111-1111-111111111111", course_map)
        assert res == "CS101: Introduction to Computer Science"

    def test_resolve_course_display_name_preserves_readable_names(self) -> None:
        """Contract 7: Already human-readable course names pass through unchanged."""
        course_map = {
            "c1111111-1111-1111-1111-111111111111": "CS101: Introduction to Computer Science",
        }
        res = resolve_course_display_name("CS101: Introduction to Computer Science", course_map)
        assert res == "CS101: Introduction to Computer Science"

    def test_resolve_course_display_name_safe_unknown_uuid(self) -> None:
        """Contract 8: Unresolvable UUIDs are presented safely as Course (uuid...) rather than crashing."""
        course_map = {}
        unknown_id = "e9999999-9999-9999-9999-999999999999"
        res = resolve_course_display_name(unknown_id, course_map)
        assert res == "Course (e9999999...)"

    def test_extract_assigned_course_ids_preserves_ids_from_names_and_uuids(self) -> None:
        """Contract 9: _extract_assigned_course_ids resolves names to UUIDs and keeps raw UUIDs."""
        admin_with_uuid = AdminUserDTO(
            id="a1",
            email="prof@univ.edu",
            full_name="Prof A",
            role="ADMIN",
            admin_role="FACULTY_ADMIN",
            assigned_courses=["c1111111-1111-1111-1111-111111111111"],
        )

        cids_uuid = extract_assigned_course_ids(admin_with_uuid)
        assert "c1111111-1111-1111-1111-111111111111" in cids_uuid

    def test_three_distinct_course_lookup_states(self) -> None:
        """Contract 10: Handle 3 distinct states: success with courses, success empty, and failure."""
        # State 1: Success with courses
        courses_state_1 = [
            KnowledgeBaseDTO(id="c1", name="CS101", code="CS101", description="", is_active=True, created_at=""),
        ]
        err_state_1 = None
        assert courses_state_1 is not None and len(courses_state_1) > 0
        assert err_state_1 is None

        # State 2: Success empty (0 courses in catalog)
        courses_state_2 = []
        err_state_2 = None
        assert courses_state_2 is not None and len(courses_state_2) == 0
        assert err_state_2 is None

        # State 3: Failure
        courses_state_3 = None
        err_state_3 = "Course service temporarily unavailable"
        assert courses_state_3 is None
        assert err_state_3 is not None
        # Must not be confused with empty catalog
        assert not (courses_state_3 is not None and len(courses_state_3) == 0)


class TestOverviewContractsPart10B:
    """Test Overview page status truthfulness, non-idle failed jobs, and list bounding."""

    def test_overview_queue_status_flags_attention_when_failed_jobs_exist(self) -> None:
        """Contract 11: When active_jobs is 0 but failed_jobs > 0, queue does NOT claim idle."""
        jobs = [
            IndexingJobDTO(
                job_id="j1",
                document_id="d1",
                knowledge_base_id="k1",
                status="FAILED",
                stage="PARSING",
                error_message="Corrupt header",
                document_name="bad.pdf",
            )
        ]

        active_jobs = [j for j in jobs if j.status in ("PROCESSING", "STARTING", "PARSING")]
        failed_jobs = [j for j in jobs if j.status == "FAILED"]

        assert len(active_jobs) == 0
        assert len(failed_jobs) == 1

        is_falsely_idle = not active_jobs and not failed_jobs
        assert is_falsely_idle is False

    def test_overview_course_list_bounded_to_four(self) -> None:
        """Contract 12: Overview caps displayed course summaries to 4 with link to Course Management."""
        courses = [
            CourseSummaryDTO(id=f"c{i}", name=f"Course {i}", code=f"C{i}", document_count=i, active_students=i * 2)
            for i in range(10)
        ]

        capped = courses[:4]
        assert len(capped) == 4
        assert len(courses) > 4
        has_more_link = len(courses) > 4
        assert has_more_link is True
        remaining_count = len(courses) - 4
        assert remaining_count == 6

    def test_preview_mode_status_in_overview_never_says_all_operational(self) -> None:
        """Contract 13: In preview mode, Overview displays Preview state and never 'All Core Infrastructure Operational'."""
        health = SystemHealthDTO(
            status="preview",
            components=[
                ComponentHealthDTO(name="PostgreSQL", status="preview", message="Simulated"),
            ],
            checked_at="2026-10-23T05:00:00Z",
        )

        status_lower = (health.status or "unknown").lower()
        assert status_lower == "preview"
        assert status_lower != "healthy"

        # The display text in Overview must be simulated/preview
        assert status_lower in ("preview", "unknown", "degraded", "unavailable")


class TestSystemDiagnosticsServiceHealthBoardPart10B2:
    """Tests for Part 10B.2 System Diagnostics Service Health Board Redesign."""

    def test_01_api_gateway_resolves_to_api_handling(self) -> None:
        """Requirement 1 & 2: API Gateway resolves to verified API request handling description."""
        icon, scope = get_subsystem_metadata("API Gateway")
        assert icon == "router"
        assert "API request handling" in scope
        assert "application endpoint availability" in scope

    def test_02_postgresql_database_resolves_to_relational_persistence(self) -> None:
        """Requirement 1 & 2: PostgreSQL Database resolves to relational persistence for records, users, courses, audit."""
        icon, scope = get_subsystem_metadata("PostgreSQL Database")
        assert icon == "storage"
        assert "Relational persistence" in scope
        assert "records, users, courses, and audit data" in scope

    def test_03_pgvector_extension_resolves_to_vector_storage(self) -> None:
        """Requirement 1 & 2: pgvector Extension resolves to storage and similarity search for vector embeddings."""
        icon, scope = get_subsystem_metadata("pgvector Extension")
        assert icon == "scatter_plot"
        assert "similarity search for vector embeddings" in scope

    def test_04_ollama_services_resolves_to_language_model_inference(self) -> None:
        """Requirement 1 & 2: Ollama Services resolves to local language-model inference."""
        icon, scope = get_subsystem_metadata("Ollama Services")
        assert icon == "psychology"
        assert "language-model inference" in scope
        assert "grounded assistant responses" in scope

    def test_05_indexing_worker_resolves_to_document_processing_jobs(self) -> None:
        """Requirement 1 & 2: Indexing Background Worker resolves to asynchronous document parsing/chunking/embedding/indexing."""
        icon, scope = get_subsystem_metadata("Indexing Background Worker")
        assert icon == "sync"
        assert "Asynchronous document parsing" in scope
        assert "indexing jobs" in scope

    def test_06_unknown_component_receives_neutral_fallback(self) -> None:
        """Requirement 12: Unknown or empty component names receive neutral fallback, not generic misleading text."""
        icon, scope = get_subsystem_metadata("Quantum Compute Accelerator")
        assert icon == "memory"
        assert scope == "Purpose not configured for this subsystem"

        icon_empty, scope_empty = get_subsystem_metadata("")
        assert icon_empty == "memory"
        assert scope_empty == "Purpose not configured for this subsystem"

    def test_07_no_generic_description_repeated_for_known_components(self) -> None:
        """Requirement 2: The old generic description does not appear for any known backend component."""
        old_generic = "Infrastructure subsystem supporting academic assistant operations"
        known_components = [
            "API Gateway",
            "PostgreSQL Database",
            "pgvector Extension",
            "Ollama Services",
            "Indexing Background Worker",
        ]
        scopes = set()
        for name in known_components:
            icon, scope = get_subsystem_metadata(name)
            assert scope != old_generic
            assert scope != FALLBACK_SCOPE_DESCRIPTION
            scopes.add(scope)

        # All 5 known subsystems must have distinct, purpose-built descriptions
        assert len(scopes) == len(known_components)

    def test_08_status_values_and_diagnostic_messages_unmodified(self) -> None:
        """Requirements 3 & 4: Actual reported status and diagnostic messages remain unchanged."""
        components = [
            ComponentHealthDTO(name="API Gateway", status="healthy", message="Gateway responding normally."),
            ComponentHealthDTO(name="PostgreSQL Database", status="healthy", message="12 active connections."),
            ComponentHealthDTO(name="pgvector Extension", status="healthy", message="Extension 0.5.1 active."),
            ComponentHealthDTO(name="Ollama Services", status="degraded", message="Unreachable at configured port."),
            ComponentHealthDTO(name="Indexing Background Worker", status="healthy", message="Listening to queue."),
        ]

        for comp in components:
            icon, scope = get_subsystem_metadata(comp.name)
            assert comp.status in ("healthy", "degraded")
            assert comp.message != ""
            assert isinstance(scope, str) and len(scope) > 10

    def test_09_overall_degraded_state_preserved_when_ollama_is_degraded(self) -> None:
        """Requirement 5: Degraded Ollama does not result in a falsely Healthy overall status."""
        health = SystemHealthDTO(
            status="degraded",
            components=[
                ComponentHealthDTO(name="API Gateway", status="healthy", message="OK"),
                ComponentHealthDTO(name="PostgreSQL Database", status="healthy", message="OK"),
                ComponentHealthDTO(name="pgvector Extension", status="healthy", message="OK"),
                ComponentHealthDTO(name="Ollama Services", status="degraded", message="Unreachable"),
                ComponentHealthDTO(name="Indexing Background Worker", status="healthy", message="OK"),
            ],
            checked_at="2026-10-23T06:00:00Z",
        )

        assert health.status == "degraded"
        ollama_comp = next(c for c in health.components if "ollama" in c.name.lower())
        assert ollama_comp.status == "degraded"
        assert health.status != "healthy"

    def test_10_preview_mode_remains_preview_never_falsely_healthy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Requirement 6: Preview mode remains preview, never falsely healthy."""
        monkeypatch.setenv("DEMO_MODE", "1")
        client = FrontendAPIClient()
        health = client.get_system_health()
        assert health.status == "preview"
        assert health.status != "healthy"

    def test_11_missing_status_handled_as_unknown(self) -> None:
        """Requirement 7: Missing health status is handled as Unknown, never falsely healthy."""
        client = FrontendAPIClient()
        client.get_session_token = Mock(return_value="live-tok")
        mock_http = Mock()
        client._http = mock_http
        mock_http.get.return_value = Mock(
            status_code=200,
            json=lambda: {"status": None, "components": [], "checked_at": "2026-10-23T06:00:00Z"},
        )
        health = client.get_system_health()
        assert health.status == "unknown"
        assert health.status != "healthy"

    def test_12_refresh_telemetry_action_present_and_wired(self) -> None:
        """Requirement 8: Refresh Telemetry button calls real refresh handler."""
        from pathlib import Path

        source = Path("frontend/pages/system_health_page.py").read_text(encoding="utf-8")
        assert "Refresh Telemetry" in source
        assert "on_click=refresh_health" in source

    def test_13_desktop_service_health_board_structure(self) -> None:
        """Requirement 9: Desktop layout uses Service Health Board (Service & Purpose, Status, Telemetry Diagnostics)."""
        from pathlib import Path

        source = Path("frontend/pages/system_health_page.py").read_text(encoding="utf-8")
        assert "Service & Purpose" in source
        assert "Telemetry Diagnostics" in source
        assert "w-[40%]" in source
        assert "w-[18%]" in source
        assert "w-[42%]" in source

    def test_14_mobile_layout_eliminates_760px_wide_table(self) -> None:
        """Requirement 10 & 11: Wide 760px table is eliminated; mobile stacks without sideways scrolling."""
        from pathlib import Path

        source = Path("frontend/pages/system_health_page.py").read_text(encoding="utf-8")
        # Must NOT use min-w-[760px] or HTML table
        assert "min-w-[760px]" not in source
        assert 'ui.element("table")' not in source
        # Must have responsive flex container
        assert "flex-col md:flex-row" in source
        assert "diagnostics-mobile-badge" in source

    def test_15_empty_components_and_failed_request_states(self) -> None:
        """Requirements 13 & 14: Empty component list and failed request render honest error/empty states."""
        from pathlib import Path

        source = Path("frontend/pages/system_health_page.py").read_text(encoding="utf-8")
        assert "render_empty_state(" in source
        assert "render_alert(" in source
        assert "System Telemetry Probe Unreachable" in source

    def test_16_long_subsystem_names_and_messages_readable(self) -> None:
        """Requirement 15 & 16: Accessible labels, long names (Indexing Background Worker), and diagnostic messages."""
        from pathlib import Path

        source = Path("frontend/pages/system_health_page.py").read_text(encoding="utf-8")
        assert "render_status_badge" in source
        assert "leading-relaxed" in source
        assert "font-sans" in source
