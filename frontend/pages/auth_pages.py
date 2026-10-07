"""
Public Entry and Authentication Presentation Pages.

Provides the complete public-facing academic software experience:
- /login: Primary landing and portal entry with hero, product demonstration,
  four core academic value pillars, dual student/admin gateways, and trust guarantees.
- /student/login: Dedicated Student Portal authentication with split-pane academic guidance.
- /admin/login: Dedicated Administrator Portal authentication with governance and security context.
- /register: Dedicated student onboarding and registration interface.

Strictly preserves server-side role enforcement (STUDENT vs ADMIN), HttpOnly session cookies,
and centralized error normalization via normalize_error().
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.components.layout import _handle_logout, auth_layout
from frontend.components.ui_kit import render_alert


def _render_authenticated_notice(current_role: str, user_email: str, target_portal: str) -> None:
    """Render structured guidance when an authenticated user visits the opposite role portal."""
    with auth_layout(max_width_class="max-w-xl", page_type=target_portal):
        with ui.card().classes(
            "w-full p-8 bg-white border border-slate-200 rounded-xl shadow-xs text-center items-center my-8 box-border"
        ):
            with ui.element("div").classes(
                "w-12 h-12 rounded-full bg-blue-50 text-blue-700 flex items-center justify-center mb-3"
            ):
                ui.icon("info", size="24px")

            ui.label("Account Role Conflict").classes("text-xl font-bold text-slate-900 tracking-tight")
            ui.label(
                f"You are currently signed in as a {current_role.title()} ({user_email}). "
                f"The {target_portal.title()} Portal requires {target_portal.lower()} privileges."
            ).classes("text-sm text-slate-600 max-w-md mt-2 leading-relaxed")

            with ui.column().classes("w-full max-w-xs gap-3 mt-6 mx-auto"):
                ui.button(
                    "Go to Your Dashboard",
                    icon="dashboard",
                    on_click=lambda: ui.navigate.to("/dashboard"),
                ).props("no-caps").classes(
                    "w-full py-2.5 font-medium text-sm rounded-lg !bg-slate-900 hover:!bg-slate-800 !text-white shadow-xs transition-colors"
                )

                ui.button(
                    "Sign Out of Current Account",
                    icon="logout",
                    on_click=_handle_logout,
                ).props("outline no-caps").classes(
                    "w-full py-2.5 font-medium text-sm text-slate-700 border-slate-300 rounded-lg hover:bg-slate-50"
                )


def _render_login_form(portal: str, allowed_role: str) -> None:
    """
    Render a balanced split-pane login interface for Student or Administrator portals.

    :param portal: 'student' or 'admin'
    :param allowed_role: 'STUDENT' or 'ADMIN'
    """
    current_user = api_client.get_current_user()
    if current_user is not None:
        if current_user.role == allowed_role:
            ui.navigate.to("/dashboard")
            return
        _render_authenticated_notice(
            current_role=current_user.role,
            user_email=current_user.email,
            target_portal=portal,
        )
        return

    is_student = allowed_role == "STUDENT"

    with auth_layout(max_width_class="max-w-5xl", page_type=portal):
        # Two-Column Composition: Academic Context on Left, Focused Form on Right
        with ui.element("div").classes(
            "w-full grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-start my-2 sm:my-4 box-border"
        ):
            # Left Column: Product & Institutional Context
            with ui.column().classes("order-2 lg:order-1 lg:col-span-6 gap-5"):
                with ui.row().classes("items-center gap-2"):
                    with ui.element("div").classes(
                        "w-7 h-7 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold"
                        if is_student
                        else "w-7 h-7 rounded-lg bg-slate-100 text-slate-800 flex items-center justify-center font-bold"
                    ):
                        ui.icon("school" if is_student else "admin_panel_settings", size="16px")
                    ui.label("STUDENT GATEWAY" if is_student else "FACULTY & ADMINISTRATION").classes(
                        "text-xs font-bold uppercase tracking-wider text-slate-500"
                    )

                ui.label(
                    "Access your course materials with grounded intelligence."
                    if is_student
                    else "Academic content management and vector index governance."
                ).classes("text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight")

                ui.label(
                    "Sign in to ask natural questions across your enrolled course syllabi, lecture slides, and academic guidelines with verified in-browser citations."
                    if is_student
                    else "Authorized administration portal for faculty members and administrators to curate course materials, verify chunk indices, and manage RBAC access."
                ).classes("text-sm sm:text-base text-slate-600 leading-relaxed")

                # Institutional Context Highlights
                with ui.column().classes("w-full gap-3 pt-2"):
                    if is_student:
                        student_features = [
                            ("find_in_page", "Verified Document Citations", "Direct page and section references for every answer."),
                            ("lock", "Enrolled Course Isolation", "Search only materials officially assigned to your cohort."),
                            ("visibility", "In-Browser PDF Viewer", "Inspect original files alongside answers without downloads."),
                        ]
                        for icon, title, desc in student_features:
                            with ui.row().classes("items-start gap-3"):
                                with ui.element("div").classes(
                                    "w-7 h-7 rounded-md bg-slate-100 text-blue-700 flex items-center justify-center shrink-0 mt-0.5"
                                ):
                                    ui.icon(icon, size="16px")
                                with ui.column().classes("gap-0"):
                                    ui.label(title).classes("text-xs font-bold text-slate-800")
                                    ui.label(desc).classes("text-xs text-slate-500 leading-relaxed")
                    else:
                        admin_features = [
                            ("menu_book", "Course Curation", "Provision knowledge bases and assign student memberships."),
                            ("folder_open", "Document Management", "Upload, partition, and maintain document lifecycles."),
                            ("security", "Server-Side RBAC", "Enforce strict departmental roles and audit access logs."),
                        ]
                        for icon, title, desc in admin_features:
                            with ui.row().classes("items-start gap-3"):
                                with ui.element("div").classes(
                                    "w-7 h-7 rounded-md bg-slate-100 text-slate-700 flex items-center justify-center shrink-0 mt-0.5"
                                ):
                                    ui.icon(icon, size="16px")
                                with ui.column().classes("gap-0"):
                                    ui.label(title).classes("text-xs font-bold text-slate-800")
                                    ui.label(desc).classes("text-xs text-slate-500 leading-relaxed")

                # Security / Policy Notice
                with ui.element("div").classes(
                    "w-full p-3.5 rounded-lg bg-slate-50 border border-slate-200 mt-2"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("verified_user", size="16px").classes(
                            "text-blue-700" if is_student else "text-slate-700"
                        )
                        ui.label(
                            "Institutional Security Enforced"
                            if is_student
                            else "Restricted Administrative Area"
                        ).classes("text-xs font-bold text-slate-800")
                    ui.label(
                        "All student queries are bound strictly to assigned courses. Zero external data sharing."
                        if is_student
                        else "All administrative sessions and indexing actions are recorded and audited server-side."
                    ).classes("text-xs text-slate-500 mt-1")

            # Right Column: Focused Authentication Form
            with ui.column().classes("order-1 lg:order-2 lg:col-span-6 w-full"):
                with ui.card().classes(
                    "w-full max-w-[460px] mx-auto p-5 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-xs box-border overflow-hidden"
                ):
                    # Form Navigation Header
                    with ui.row().classes("w-full justify-between items-center mb-4"):
                        with (
                            ui.link(target="/login")
                            .classes(
                                "inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors no-underline py-1 px-2 -ml-2 rounded-md hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-blue-600"
                            )
                            .props('aria-label="Back to portal selection"')
                        ):
                            ui.icon("arrow_back", size="14px").classes("text-slate-500")
                            ui.label("Back to home").classes("text-xs font-medium")

                        ui.badge(
                            "Student Sign In" if is_student else "Admin Sign In",
                            color="blue-1" if is_student else "slate-2",
                        ).props("text-color=blue-9" if is_student else "text-color=slate-8").classes(
                            "text-[10px] font-bold px-2 py-0.5 border "
                            + ("border-blue-200" if is_student else "border-slate-300")
                        )

                    with ui.column().classes("w-full gap-1 mb-5"):
                        ui.label("Student Sign In" if is_student else "Administrator Sign In").classes(
                            "text-xl sm:text-2xl font-bold text-slate-900 tracking-tight"
                        )
                        ui.label(
                            "Enter your institutional email address and password."
                            if is_student
                            else "Enter your administrator or faculty credentials."
                        ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                    # Inline error alert container
                    error_container = ui.column().classes("w-full mb-3")

                    # Explicit Accessible Form Controls
                    with ui.column().classes("w-full gap-1.5 mb-3.5"):
                        ui.label("Institutional Email").classes(
                            "text-xs font-semibold uppercase tracking-wider text-slate-700"
                        )
                        email_input = (
                            ui.input(
                                placeholder="student@university.edu"
                                if is_student
                                else "admin@university.edu"
                            )
                            .props("outlined dense type=email")
                            .classes("w-full minimalist-input")
                        )

                    with ui.column().classes("w-full gap-1.5 mb-5"):
                        ui.label("Password").classes(
                            "text-xs font-semibold uppercase tracking-wider text-slate-700"
                        )
                        password_input = (
                            ui.input(
                                placeholder="••••••••",
                                password=True,
                                password_toggle_button=True,
                            )
                            .props("outlined dense")
                            .classes("w-full minimalist-input")
                        )

                    def handle_submit() -> None:
                        error_container.clear()
                        email = (email_input.value or "").strip()
                        password = password_input.value or ""

                        if not email or "@" not in email:
                            with error_container:
                                render_alert("Please enter a valid institutional email address.", "warning")
                            return

                        if not password:
                            with error_container:
                                render_alert("Password is required.", "warning")
                            return

                        submit_btn.props("loading disable")
                        submit_btn.text = "Authenticating..."

                        try:
                            if is_student:
                                user = api_client.student_login(email=email, password=password)
                            else:
                                user = api_client.admin_login(email=email, password=password)

                            ui.notify(
                                f"Authenticated successfully. Welcome, {user.full_name}!",
                                type="positive",
                            )
                            ui.navigate.to("/dashboard")
                        except ValueError as err:
                            with error_container:
                                render_alert(normalize_error(err, context="auth"), "negative")
                        finally:
                            submit_btn.props(remove="loading disable")
                            submit_btn.text = "Sign in as Student" if is_student else "Sign in as Administrator"

                    email_input.on("keydown.enter", handle_submit)
                    password_input.on("keydown.enter", handle_submit)

                    with ui.column().classes("w-full gap-2.5"):
                        submit_btn = (
                            ui.button(
                                "Sign in as Student" if is_student else "Sign in as Administrator",
                                icon="login" if is_student else "security",
                                on_click=handle_submit,
                            )
                            .props("no-caps")
                            .classes(
                                "w-full py-2.5 font-medium text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs transition-colors"
                                if is_student
                                else "w-full py-2.5 font-medium text-sm rounded-lg !bg-slate-900 hover:!bg-slate-800 !text-white shadow-xs transition-colors"
                            )
                        )

                    # Footer Cross-Portal Links
                    with ui.column().classes(
                        "w-full items-center text-center mt-5 pt-4 border-t border-slate-100 gap-1.5 text-xs text-slate-500"
                    ):
                        if is_student:
                            with ui.row().classes("justify-center items-center gap-1.5 flex-wrap"):
                                ui.label("Need an account?")
                                ui.link("Register as Student", "/register").classes(
                                    "text-blue-700 font-semibold hover:underline no-underline"
                                )
                            with ui.row().classes("justify-center items-center gap-1.5 flex-wrap mt-1"):
                                ui.label("Faculty or staff?")
                                ui.link("Administrator Sign In", "/admin/login").classes(
                                    "text-slate-700 font-semibold hover:underline no-underline"
                                )
                        else:
                            with ui.row().classes("justify-center items-center gap-1.5 flex-wrap"):
                                ui.label("Looking for student access?")
                                ui.link("Student Sign In", "/student/login").classes(
                                    "text-blue-700 font-semibold hover:underline no-underline"
                                )
                            ui.label("Administrative accounts are provisioned internally by IT.").classes(
                                "text-[11px] text-slate-400 mt-1"
                            )


def register_auth_pages() -> None:
    """Register all public authentication and portal routing handlers."""

    @ui.page("/login")
    def login_portal_page() -> None:
        """
        Public Landing and Gateway Selection Page.

        Communicates what RAG Assistant is, who it is for, how it works, and
        provides clear primary actions into student and administrator experiences.
        """
        current_user = api_client.get_current_user()

        with auth_layout(max_width_class="max-w-6xl", page_type="landing"):
            # Authenticated Banner Notice if already logged in
            if current_user:
                with ui.element("div").classes(
                    "w-full p-4 mb-8 bg-blue-50 border border-blue-200 rounded-xl flex items-center justify-between gap-4 flex-wrap"
                ):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("account_circle", size="24px").classes("text-blue-700")
                        with ui.column().classes("gap-0"):
                            ui.label(f"Active Session: {current_user.full_name}").classes(
                                "text-sm font-bold text-slate-900"
                            )
                            ui.label(
                                f"Signed in as {current_user.role.title()} ({current_user.email})"
                            ).classes("text-xs text-slate-600")
                    with ui.row().classes("items-center gap-2"):
                        ui.button(
                            "Continue to Dashboard",
                            icon="dashboard",
                            on_click=lambda: ui.navigate.to("/dashboard"),
                        ).props("no-caps dense").classes(
                            "px-3.5 py-1.5 text-xs font-semibold rounded-lg !bg-slate-900 hover:!bg-slate-800 !text-white"
                        )
                        ui.button(
                            "Sign Out",
                            on_click=_handle_logout,
                        ).props("outline no-caps dense").classes(
                            "px-3 py-1.5 text-xs font-medium rounded-lg text-slate-700 border-slate-300 hover:bg-white"
                        )

            # ------------------------------------------------------------------
            # 1. Primary Intro & Hero Viewport
            # ------------------------------------------------------------------
            with ui.element("section").classes("w-full py-4 sm:py-8"):
                with ui.column().classes("w-full max-w-3xl gap-4"):
                    # Institutional Badge
                    with ui.row().classes("items-center gap-2"):
                        ui.badge("Academic Knowledge Platform", color="blue-1").props(
                            "text-color=blue-9"
                        ).classes("text-xs font-bold px-2.5 py-1 border border-blue-200")
                        ui.label("Multi-Format Text RAG System").classes(
                            "text-xs font-medium text-slate-500"
                        )

                    # Primary Value Headline
                    ui.label("Grounded Knowledge Assistant for University Courses").classes(
                        "text-3xl sm:text-4xl lg:text-5xl font-extrabold text-slate-900 tracking-tight leading-[1.15]"
                    )

                    # Concise Supporting Paragraph
                    ui.label(
                        "Ask natural questions across your enrolled course syllabi, lecture materials, and academic guidelines. "
                        "Receive precise, evidence-backed answers with verifiable in-browser source citations from official documents."
                    ).classes("text-base sm:text-lg text-slate-600 leading-relaxed max-w-2xl")

                    # Primary Call to Action Controls
                    with ui.row().classes("items-center gap-3 pt-2 flex-wrap w-full"):
                        ui.button(
                            "Sign in as Student",
                            icon="login",
                            on_click=lambda: ui.navigate.to("/student/login"),
                        ).props("no-caps").classes(
                            "w-full sm:w-auto px-5 py-2.5 font-semibold text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs transition-colors"
                        )

                        ui.button(
                            "Administrator Sign In",
                            icon="security",
                            on_click=lambda: ui.navigate.to("/admin/login"),
                        ).props("outline no-caps").classes(
                            "w-full sm:w-auto px-4 py-2.5 font-semibold text-sm rounded-lg text-slate-800 border-slate-300 hover:bg-slate-100 transition-colors"
                        )

                        with (
                            ui.link("New student? Register account →", "/register")
                            .classes(
                                "text-xs sm:text-sm font-semibold text-blue-700 hover:underline no-underline px-1 py-1"
                            )
                        ):
                            pass

            # ------------------------------------------------------------------
            # 2. Live Grounded Evidence Demonstration Card (Product Proof)
            # ------------------------------------------------------------------
            with ui.element("section").classes("w-full my-6 box-border"):
                with ui.card().classes(
                    "w-full p-6 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-xs box-border"
                ):
                    with ui.row().classes("w-full justify-between items-center mb-4 flex-wrap gap-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("verified", size="18px").classes("text-blue-700")
                            ui.label("Grounded Retrieval & Citation Architecture").classes(
                                "text-xs font-bold uppercase tracking-wider text-slate-700"
                            )
                        ui.badge("Live Workflow Demonstration", color="slate-1").props(
                            "text-color=slate-7"
                        ).classes("text-[11px] font-medium px-2 py-0.5 border border-slate-200")

                    # Query Example
                    with ui.element("div").classes(
                        "w-full p-3.5 bg-slate-50 border border-slate-200 rounded-lg mb-3"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("help_outline", size="16px").classes("text-slate-500")
                            ui.label("Student Question:").classes("text-xs font-bold text-slate-700")
                        ui.label(
                            '"What is the policy for late assignment submissions in Advanced Algorithms (CS-301)?"'
                        ).classes("text-sm text-slate-900 font-medium mt-1")

                    # Assistant Verified Answer
                    with ui.element("div").classes(
                        "w-full p-4 bg-white border border-blue-200 rounded-lg mb-3"
                    ):
                        with ui.row().classes("items-center gap-2 mb-1.5"):
                            with ui.element("div").classes(
                                "w-5 h-5 rounded bg-blue-700 text-white flex items-center justify-center font-bold text-[10px]"
                            ):
                                ui.label("A")
                            ui.label("Assistant Response with Inline Evidence Attribution").classes(
                                "text-xs font-bold text-blue-900"
                            )
                        ui.label(
                            "Late submissions are accepted up to 72 hours following the deadline with a 10% penalty per 24-hour period. "
                            "Submissions past three calendar days receive zero credit unless supported by an authorized medical exemption [1]."
                        ).classes("text-sm text-slate-800 leading-relaxed")

                    # Grounded Citation Card
                    with ui.element("div").classes(
                        "w-full p-3.5 bg-slate-50 border border-slate-200 rounded-lg"
                    ):
                        with ui.row().classes("items-center justify-between gap-2 flex-wrap"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("description", size="16px").classes("text-blue-700")
                                ui.label("[1] CS301_Syllabus_Fall2026.pdf").classes(
                                    "text-xs font-bold text-slate-900 font-mono"
                                )
                                ui.label("• Page 4, Section 3.2 Evaluation Policies").classes(
                                    "text-xs text-slate-500"
                                )
                            ui.badge("Verified Grounding", color="green-1").props(
                                "text-color=green-9"
                            ).classes("text-[10px] font-bold px-2 py-0.5 border border-green-200")

                        ui.label(
                            '"Section 3.2 Late Work: Submissions delayed past the deadline are subject to a 10% deduction per 24-hour period for up to three calendar days. Beyond this window, unsubmitted coursework will receive no marks."'
                        ).classes("text-xs text-slate-600 italic mt-2 pl-3 border-l-2 border-blue-300 leading-relaxed")

            # ------------------------------------------------------------------
            # 3. Product Value Pillars (Four Core Capabilities)
            # ------------------------------------------------------------------
            with ui.element("section").classes("w-full my-8 box-border"):
                with ui.column().classes("w-full gap-2 mb-6"):
                    ui.label("Engineered for Academic Precision").classes(
                        "text-2xl font-bold text-slate-900 tracking-tight"
                    )
                    ui.label(
                        "Four foundational principles guarantee factual accuracy, course isolation, and institutional governance."
                    ).classes("text-sm text-slate-600 leading-relaxed")

                with ui.element("div").classes(
                    "w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 box-border"
                ):
                    pillars = [
                        (
                            "lock",
                            "Course-Scoped Access",
                            "Students only search materials from officially assigned courses. Zero unauthorized course leakage.",
                        ),
                        (
                            "find_in_page",
                            "Verifiable Citations",
                            "Every factual claim attributes exact document titles, page numbers, and quoted evidence excerpts.",
                        ),
                        (
                            "folder_open",
                            "Multi-Format Ingestion",
                            "Native support for university course documents in PDF, DOCX, TXT, Markdown, and CSV formats.",
                        ),
                        (
                            "verified_user",
                            "Institution-Governed",
                            "Course syllabi and files are curated, versioned, and activated directly by university faculty and administrators.",
                        ),
                    ]
                    for icon, title, desc in pillars:
                        with ui.card().classes(
                            "w-full p-5 bg-white border border-slate-200 rounded-xl shadow-xs flex flex-col justify-between box-border"
                        ):
                            with ui.column().classes("gap-2.5"):
                                with ui.element("div").classes(
                                    "w-9 h-9 rounded-lg bg-slate-100 text-blue-700 flex items-center justify-center"
                                ):
                                    ui.icon(icon, size="20px")
                                ui.label(title).classes("text-sm font-bold text-slate-900")
                                ui.label(desc).classes("text-xs text-slate-600 leading-relaxed")

            # ------------------------------------------------------------------
            # 4. User Journey Selection (Student vs Administrator Gateways)
            # ------------------------------------------------------------------
            with ui.element("section").classes("w-full my-8 box-border"):
                with ui.column().classes("w-full gap-1 mb-6 text-center items-center"):
                    ui.label("Select Your University Gateway").classes(
                        "text-2xl font-bold text-slate-900 tracking-tight"
                    )
                    ui.label(
                        "Tailored workflows designed specifically for student learning and academic administration."
                    ).classes("text-sm text-slate-600 max-w-lg leading-relaxed")

                with ui.element("div").classes(
                    "w-full grid grid-cols-1 lg:grid-cols-2 gap-6 box-border"
                ):
                    # Student Portal Card
                    with ui.card().classes(
                        "w-full p-6 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-blue-300 transition-colors flex flex-col justify-between box-border"
                    ):
                        with ui.column().classes("w-full gap-4"):
                            with ui.row().classes("w-full justify-between items-center"):
                                with ui.element("div").classes(
                                    "w-10 h-10 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold"
                                ):
                                    ui.icon("school", size="22px")
                                ui.badge("Student Access", color="blue-1").props(
                                    "text-color=blue-9"
                                ).classes("text-[10px] font-bold px-2 py-0.5 border border-blue-200")

                            with ui.column().classes("gap-1"):
                                ui.label("Student Portal").classes(
                                    "text-xl font-bold text-slate-900 tracking-tight"
                                )
                                ui.label(
                                    "Inquire across enrolled university courses, research syllabus topics, and verify citations."
                                ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                            # Feature bullet points
                            with ui.column().classes("w-full gap-2 pt-2"):
                                student_bullets = [
                                    "Query across all your assigned courses in one conversational workspace",
                                    "Inspect exact document page numbers and text evidence in-browser",
                                    "Zero hallucination safeguards: unverified claims are rejected",
                                ]
                                for bullet in student_bullets:
                                    with ui.row().classes("items-start gap-2"):
                                        ui.icon("check_circle", size="14px").classes("text-blue-700 mt-0.5")
                                        ui.label(bullet).classes("text-xs text-slate-600 leading-relaxed")

                        with ui.column().classes("w-full mt-6 gap-2.5"):
                            ui.button(
                                "Student Sign In",
                                icon="login",
                                on_click=lambda: ui.navigate.to("/student/login"),
                            ).props("no-caps").classes(
                                "w-full py-2.5 font-medium text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs transition-colors"
                            )
                            with ui.row().classes("w-full justify-center text-xs text-slate-500 gap-1.5"):
                                ui.label("Need a student account?")
                                ui.link("Register as Student", "/register").classes(
                                    "text-blue-700 font-semibold hover:underline no-underline"
                                )

                    # Administrator Portal Card
                    with ui.card().classes(
                        "w-full p-6 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-slate-400 transition-colors flex flex-col justify-between box-border"
                    ):
                        with ui.column().classes("w-full gap-4"):
                            with ui.row().classes("w-full justify-between items-center"):
                                with ui.element("div").classes(
                                    "w-10 h-10 rounded-lg bg-slate-100 text-slate-800 flex items-center justify-center font-bold"
                                ):
                                    ui.icon("admin_panel_settings", size="22px")
                                ui.badge("Staff Only", color="slate-2").props(
                                    "text-color=slate-8"
                                ).classes("text-[10px] font-bold px-2 py-0.5 border border-slate-300")

                            with ui.column().classes("gap-1"):
                                ui.label("Administrator Portal").classes(
                                    "text-xl font-bold text-slate-900 tracking-tight"
                                )
                                ui.label(
                                    "Curate university courses, upload & chunk documents, monitor vector indexing, and manage access."
                                ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                            # Feature bullet points
                            with ui.column().classes("w-full gap-2 pt-2"):
                                admin_bullets = [
                                    "Provision course knowledge bases and configure student enrollments",
                                    "Manage multi-format document lifecycles and toggle active retrieval",
                                    "Monitor vector indexing jobs, chunk validation, and telemetry diagnostics",
                                ]
                                for bullet in admin_bullets:
                                    with ui.row().classes("items-start gap-2"):
                                        ui.icon("check_circle", size="14px").classes("text-slate-700 mt-0.5")
                                        ui.label(bullet).classes("text-xs text-slate-600 leading-relaxed")

                        with ui.column().classes("w-full mt-6 gap-2.5"):
                            ui.button(
                                "Administrator Sign In",
                                icon="security",
                                on_click=lambda: ui.navigate.to("/admin/login"),
                            ).props("no-caps").classes(
                                "w-full py-2.5 font-medium text-sm rounded-lg !bg-slate-900 hover:!bg-slate-800 !text-white shadow-xs transition-colors"
                            )
                            ui.label("Accounts are provisioned by university administration.").classes(
                                "text-xs text-slate-400 text-center"
                            )

            # ------------------------------------------------------------------
            # 5. Academic Trust & Security Banner
            # ------------------------------------------------------------------
            with ui.element("section").classes("w-full my-8 box-border"):
                with ui.card().classes(
                    "w-full p-6 sm:p-8 bg-slate-900 text-white rounded-xl shadow-xs box-border"
                ):
                    with ui.row().classes("w-full justify-between items-start gap-6 flex-wrap"):
                        with ui.column().classes("max-w-xl gap-2"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("shield", size="20px").classes("text-blue-400")
                                ui.label("Institutional Trust & Privacy Standards").classes(
                                    "text-lg font-bold text-white tracking-tight"
                                )
                            ui.label(
                                "RAG Assistant operates strictly on university-controlled infrastructure. "
                                "Student inquiries are strictly membership-isolated, and generated responses "
                                "are deterministically bounded to retrieved document evidence."
                            ).classes("text-xs sm:text-sm text-slate-300 leading-relaxed")

                        with ui.column().classes("gap-2 text-xs text-slate-300"):
                            ui.label("✓ Argon2id Secure Password Hashing").classes("font-medium")
                            ui.label("✓ HttpOnly Session Token Jar").classes("font-medium")
                            ui.label("✓ Multi-Format Text Verification").classes("font-medium")
                            ui.label("✓ Server-Side Course Authorization").classes("font-medium")

            # ------------------------------------------------------------------
            # 6. Bottom Call to Action
            # ------------------------------------------------------------------
            with ui.element("section").classes(
                "w-full py-8 text-center items-center flex flex-col justify-center gap-3 box-border"
            ):
                ui.label("Ready to Study with Verified Citations?").classes(
                    "text-xl sm:text-2xl font-bold text-slate-900 tracking-tight"
                )
                ui.label(
                    "Access your course materials or contact your department for enrollment."
                ).classes("text-xs sm:text-sm text-slate-500 max-w-md")

                with ui.row().classes("items-center justify-center gap-3 mt-2 flex-wrap"):
                    ui.button(
                        "Sign in as Student",
                        icon="school",
                        on_click=lambda: ui.navigate.to("/student/login"),
                    ).props("no-caps").classes(
                        "px-4 py-2 font-semibold text-xs sm:text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs"
                    )

                    ui.button(
                        "Create Student Account",
                        icon="person_add",
                        on_click=lambda: ui.navigate.to("/register"),
                    ).props("outline no-caps").classes(
                        "px-4 py-2 font-semibold text-xs sm:text-sm rounded-lg text-slate-800 border-slate-300 hover:bg-slate-100"
                    )

                    ui.button(
                        "Administrator Access",
                        icon="admin_panel_settings",
                        on_click=lambda: ui.navigate.to("/admin/login"),
                    ).props("flat no-caps").classes(
                        "px-3 py-2 text-xs sm:text-sm font-medium text-slate-600 hover:text-slate-900"
                    )

    @ui.page("/student/login")
    def student_login_page() -> None:
        """Dedicated Student Portal sign-in screen."""
        _render_login_form(portal="student", allowed_role="STUDENT")

    @ui.page("/admin/login")
    def admin_login_page() -> None:
        """Dedicated Administrator Portal sign-in screen."""
        _render_login_form(portal="admin", allowed_role="ADMIN")

    @ui.page("/register")
    def register_page() -> None:
        """Student registration page strictly provisioning STUDENT role accounts."""
        if api_client.get_current_user() is not None:
            ui.navigate.to("/dashboard")
            return

        with auth_layout(max_width_class="max-w-5xl", page_type="register"):
            # Two-Column Composition: Onboarding Guidance on Left, Registration Form on Right
            with ui.element("div").classes(
                "w-full grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-start my-2 sm:my-4 box-border"
            ):
                # Left Column: Student Onboarding Context
                with ui.column().classes("order-2 lg:order-1 lg:col-span-6 gap-5"):
                    with ui.row().classes("items-center gap-2"):
                        with ui.element("div").classes(
                            "w-7 h-7 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold"
                        ):
                            ui.icon("school", size="16px")
                        ui.label("STUDENT ONBOARDING").classes(
                            "text-xs font-bold uppercase tracking-wider text-slate-500"
                        )

                    ui.label("Create your university student account.").classes(
                        "text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight"
                    )

                    ui.label(
                        "Register with your university email address to access your assigned course materials, research syllabi, and receive verified answers with page citations."
                    ).classes("text-sm sm:text-base text-slate-600 leading-relaxed")

                    # Onboarding Guidelines
                    with ui.column().classes("w-full gap-3 pt-2"):
                        guidelines = [
                            (
                                "mail",
                                "University Email Required",
                                "Provide your institutional email address for student verification.",
                            ),
                            (
                                "lock_outline",
                                "Password Requirements",
                                "Choose a strong password containing at least 8 characters.",
                            ),
                            (
                                "menu_book",
                                "Course Membership Linkage",
                                "Your assigned course knowledge bases will be linked by faculty administrators.",
                            ),
                        ]
                        for icon, title, desc in guidelines:
                            with ui.row().classes("items-start gap-3"):
                                with ui.element("div").classes(
                                    "w-7 h-7 rounded-md bg-slate-100 text-blue-700 flex items-center justify-center shrink-0 mt-0.5"
                                  ):
                                    ui.icon(icon, size="16px")
                                with ui.column().classes("gap-0"):
                                    ui.label(title).classes("text-xs font-bold text-slate-800")
                                    ui.label(desc).classes("text-xs text-slate-500 leading-relaxed")

                    # Already Registered Link
                    with ui.row().classes("items-center gap-1.5 pt-2 text-xs text-slate-600"):
                        ui.label("Already have an account?")
                        ui.link("Sign in to Student Portal →", "/student/login").classes(
                            "text-blue-700 font-semibold hover:underline no-underline"
                        )

                # Right Column: Registration Card
                with ui.column().classes("order-1 lg:order-2 lg:col-span-6 w-full"):
                    with ui.card().classes(
                        "w-full max-w-[460px] mx-auto p-5 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-xs box-border overflow-hidden"
                    ):
                        with ui.row().classes("w-full justify-between items-center mb-4"):
                            with (
                                ui.link(target="/login")
                                .classes(
                                    "inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors no-underline py-1 px-2 -ml-2 rounded-md hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-blue-600"
                                )
                                .props('aria-label="Back to home"')
                            ):
                                ui.icon("arrow_back", size="14px").classes("text-slate-500")
                                ui.label("Back to home").classes("text-xs font-medium")

                            ui.badge("Registration", color="blue-1").props("text-color=blue-9").classes(
                                "text-[10px] font-bold px-2 py-0.5 border border-blue-200"
                            )

                        with ui.column().classes("w-full gap-1 mb-5"):
                            ui.label("Create Student Account").classes(
                                "text-xl sm:text-2xl font-bold text-slate-900 tracking-tight"
                            )
                            ui.label(
                                "Enter your full name and university credentials to register."
                            ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                        error_container = ui.column().classes("w-full mb-3")

                        # Accessible Form Fields
                        with ui.column().classes("w-full gap-1.5 mb-3.5"):
                            ui.label("Full Name").classes(
                                "text-xs font-semibold uppercase tracking-wider text-slate-700"
                            )
                            name_input = (
                                ui.input(placeholder="Student Name")
                                .props("outlined dense")
                                .classes("w-full minimalist-input")
                            )

                        with ui.column().classes("w-full gap-1.5 mb-3.5"):
                            ui.label("University Email").classes(
                                "text-xs font-semibold uppercase tracking-wider text-slate-700"
                            )
                            email_input = (
                                ui.input(placeholder="student@university.edu")
                                .props("outlined dense type=email")
                                .classes("w-full minimalist-input")
                            )

                        with ui.column().classes("w-full gap-1.5 mb-5"):
                            ui.label("Password").classes(
                                "text-xs font-semibold uppercase tracking-wider text-slate-700"
                            )
                            password_input = (
                                ui.input(
                                    placeholder="At least 8 characters",
                                    password=True,
                                    password_toggle_button=True,
                                )
                                .props("outlined dense")
                                .classes("w-full minimalist-input")
                            )
                            ui.label("Must be at least 8 characters long.").classes(
                                "text-[11px] text-slate-400 mt-0.5"
                            )

                        def handle_register() -> None:
                            error_container.clear()
                            name = (name_input.value or "").strip()
                            email = (email_input.value or "").strip()
                            password = password_input.value or ""

                            if not name:
                                with error_container:
                                    render_alert("Full name is required.", "warning")
                                return

                            if not email or "@" not in email or "." not in email.split("@")[-1]:
                                with error_container:
                                    render_alert("Please enter a valid university email address.", "warning")
                                return

                            if len(password) < 8:
                                with error_container:
                                    render_alert("Password must be at least 8 characters long.", "warning")
                                return

                            reg_btn.props("loading disable")
                            reg_btn.text = "Creating account..."
                            try:
                                user = api_client.register(
                                    email=email,
                                    password=password,
                                    full_name=name,
                                )
                                ui.notify(
                                    f"Account created successfully. Welcome, {user.full_name}!",
                                    type="positive",
                                )
                                ui.navigate.to("/dashboard")
                            except ValueError as err:
                                with error_container:
                                    render_alert(normalize_error(err, context="auth"), "negative")
                            finally:
                                reg_btn.props(remove="loading disable")
                                reg_btn.text = "Create Student Account"

                        name_input.on("keydown.enter", handle_register)
                        email_input.on("keydown.enter", handle_register)
                        password_input.on("keydown.enter", handle_register)

                        with ui.column().classes("w-full gap-2.5"):
                            reg_btn = (
                                ui.button(
                                    "Create Student Account",
                                    icon="person_add",
                                    on_click=handle_register,
                                )
                                .props("no-caps")
                                .classes(
                                    "w-full py-2.5 font-medium text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs transition-colors"
                                )
                            )

                        with ui.column().classes(
                            "w-full items-center text-center mt-5 pt-4 border-t border-slate-100 gap-1.5"
                        ):
                            with ui.row().classes(
                                "justify-center items-center text-xs text-slate-500 gap-1.5 flex-wrap"
                            ):
                                ui.label("Already have an account?")
                                ui.link("Student Sign In", "/student/login").classes(
                                    "text-blue-700 font-semibold hover:underline no-underline"
                                )
                            with ui.row().classes(
                                "justify-center items-center text-xs text-slate-400 gap-1.5 flex-wrap mt-1"
                            ):
                                ui.label("Faculty or staff?")
                                ui.link("Administrator Sign In", "/admin/login").classes(
                                    "text-slate-700 font-semibold hover:underline no-underline"
                                )
