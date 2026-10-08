"""Public Entry and Authentication Presentation Pages.

Provides the complete editorial academic software experience:
- /login: Primary landing with editorial hero, product demonstration,
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
            "w-full p-8 bg-[#FAF6F0] border border-[#D8CFBF] rounded-lg shadow-none text-center items-center my-8 box-border"
        ):
            with ui.element("div").classes(
                "w-12 h-12 rounded-full bg-[#F3EBDD] text-[#0E1D61] border border-[#B89A5A] flex items-center justify-center mb-3"
            ):
                ui.icon("info", size="24px")

            ui.label("Account Role Conflict").classes(
                "text-2xl font-bold text-[#0E1D61] tracking-tight font-editorial"
            )
            ui.label(
                f"You are currently signed in as a {current_role.title()} ({user_email}). "
                f"The {target_portal.title()} Portal requires {target_portal.lower()} privileges."
            ).classes("text-sm text-[#3A4B7C] max-w-md mt-2 leading-relaxed")

            with ui.column().classes("w-full max-w-xs gap-3 mt-6 mx-auto"):
                ui.button(
                    "Go to Your Dashboard",
                    icon="dashboard",
                    on_click=lambda: ui.navigate.to("/dashboard"),
                ).props("no-caps").classes(
                    "w-full py-2.5 font-semibold text-sm rounded-md !bg-[#0E1D61] hover:!bg-[#1B2D7C] !text-[#FAF6F0] shadow-none transition-colors"
                )

                ui.button(
                    "Sign Out of Current Account",
                    icon="logout",
                    on_click=_handle_logout,
                ).props("outline no-caps").classes(
                    "w-full py-2.5 font-semibold text-sm text-[#0E1D61] border border-[#D8CFBF] rounded-md hover:bg-[#F5F0E8]"
                )


def _render_login_form(portal: str, allowed_role: str) -> None:
    """Render a balanced split-pane login interface for Student or Administrator portals."""
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
                        "w-7 h-7 rounded-md bg-[#0E1D61] text-[#B89A5A] flex items-center justify-center font-bold"
                    ):
                        ui.icon("school" if is_student else "admin_panel_settings", size="16px")
                    ui.label("STUDENT GATEWAY" if is_student else "FACULTY & ADMINISTRATION").classes(
                        "text-xs font-bold uppercase tracking-wider text-[#3A4B7C]"
                    )

                ui.label(
                    "Access your course materials with grounded intelligence."
                    if is_student
                    else "Academic content management and vector index governance."
                ).classes("text-2xl sm:text-3xl font-bold text-[#0E1D61] tracking-tight leading-tight font-editorial")

                ui.label(
                    "Sign in to ask natural questions across your course syllabi, lecture slides, and academic guidelines with verified in-browser citations."
                    if is_student
                    else "Authorized administration portal for faculty members and administrators to curate course materials, verify chunk indices, and manage RBAC access."
                ).classes("text-sm sm:text-base text-[#3A4B7C] leading-relaxed")

                # Institutional Context Highlights
                with ui.column().classes("w-full gap-3 pt-2"):
                    if is_student:
                        student_features = [
                            ("find_in_page", "Verified Document Citations", "Direct page and section references for every answer."),
                            ("lock", "Grounded Course Knowledge", "Search official university materials without manual enrollment."),
                            ("visibility", "In-Browser PDF Viewer", "Inspect original files alongside answers with page coordinates."),
                        ]
                        for icon, title, desc in student_features:
                            with ui.row().classes("items-start gap-3"):
                                with ui.element("div").classes(
                                    "w-7 h-7 rounded-md bg-[#F3EBDD] text-[#0E1D61] border border-[#B89A5A] flex items-center justify-center shrink-0 mt-0.5"
                                ):
                                    ui.icon(icon, size="16px")
                                with ui.column().classes("gap-0"):
                                    ui.label(title).classes("text-xs font-bold text-[#0E1D61]")
                                    ui.label(desc).classes("text-xs text-[#3A4B7C] leading-relaxed")
                    else:
                        admin_features = [
                            ("menu_book", "Course Curation", "Provision knowledge bases and configure course access rules."),
                            ("folder_open", "Document Management", "Upload, partition, and maintain document lifecycles."),
                            ("security", "Server-Side RBAC", "Enforce strict departmental roles and audit access logs."),
                        ]
                        for icon, title, desc in admin_features:
                            with ui.row().classes("items-start gap-3"):
                                with ui.element("div").classes(
                                    "w-7 h-7 rounded-md bg-[#FAF6F0] text-[#0E1D61] border border-[#D8CFBF] flex items-center justify-center shrink-0 mt-0.5"
                                ):
                                    ui.icon(icon, size="16px")
                                with ui.column().classes("gap-0"):
                                    ui.label(title).classes("text-xs font-bold text-[#0E1D61]")
                                    ui.label(desc).classes("text-xs text-[#3A4B7C] leading-relaxed")

                # Security / Policy Notice
                with ui.element("div").classes(
                    "w-full p-3.5 rounded-lg bg-[#FAF6F0] border border-[#D8CFBF] mt-2"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("verified_user", size="16px").classes("text-[#B89A5A]")
                        ui.label(
                            "Institutional Security Enforced"
                            if is_student
                            else "Restricted Administrative Area"
                        ).classes("text-xs font-bold text-[#0E1D61]")
                    ui.label(
                        "All student queries are bound strictly to authorized courses. Zero external data sharing."
                        if is_student
                        else "All administrative sessions and indexing actions are recorded and audited server-side."
                    ).classes("text-xs text-[#3A4B7C] mt-1")

            # Right Column: Focused Authentication Form
            with ui.column().classes("order-1 lg:order-2 lg:col-span-6 w-full"):
                with ui.card().classes(
                    "w-full max-w-[460px] mx-auto p-6 sm:p-8 bg-[#FAF6F0] border border-[#D8CFBF] rounded-lg shadow-none box-border overflow-hidden"
                ):
                    # Form Navigation Header
                    with ui.row().classes("w-full justify-between items-center mb-4"):
                        with (
                            ui.link(target="/login")
                            .classes(
                                "inline-flex items-center gap-1.5 text-xs font-semibold text-[#3A4B7C] hover:text-[#0E1D61] transition-colors no-underline py-1 px-2 -ml-2 rounded-md hover:bg-[#F5F0E8]"
                            )
                            .props('aria-label="Back to portal selection"')
                        ):
                            ui.icon("arrow_back", size="14px").classes("text-[#0E1D61]")
                            ui.label("Back to home").classes("text-xs font-medium")

                        ui.badge(
                            "Student Sign In" if is_student else "Admin Sign In",
                            color="amber-1",
                        ).props("text-color=brown-9").classes(
                            "text-[10px] font-bold px-2 py-0.5 border border-[#B89A5A]"
                        )

                    with ui.column().classes("w-full gap-1 mb-5"):
                        ui.label("Student Sign In" if is_student else "Administrator Sign In").classes(
                            "text-xl sm:text-2xl font-bold text-[#0E1D61] tracking-tight font-editorial"
                        )
                        ui.label(
                            "Enter your institutional email address and password."
                            if is_student
                            else "Enter your administrator or faculty credentials."
                        ).classes("text-xs sm:text-sm text-[#3A4B7C] leading-relaxed")

                    # Inline error alert container
                    error_container = ui.column().classes("w-full mb-3")

                    # Explicit Accessible Form Controls
                    with ui.column().classes("w-full gap-1.5 mb-3.5"):
                        ui.label("Institutional Email").classes(
                            "text-xs font-semibold uppercase tracking-wider text-[#3A4B7C]"
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
                            "text-xs font-semibold uppercase tracking-wider text-[#3A4B7C]"
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

                            ui.notify(f"Welcome back, {user.full_name}.", type="positive")
                            ui.navigate.to("/dashboard")
                        except ValueError as err:
                            with error_container:
                                render_alert(normalize_error(err, context="auth"), "negative")
                        finally:
                            submit_btn.props(remove="loading disable")
                            submit_btn.text = (
                                "Sign in as Student" if is_student else "Sign in as Administrator"
                            )

                    email_input.on("keydown.enter", handle_submit)
                    password_input.on("keydown.enter", handle_submit)

                    with ui.column().classes("w-full gap-3"):
                        submit_btn = (
                            ui.button(
                                "Sign in as Student" if is_student else "Sign in as Administrator",
                                icon="login",
                                on_click=handle_submit,
                            )
                            .props("no-caps")
                            .classes(
                                "w-full py-2.5 font-bold text-sm rounded-md !bg-[#0E1D61] hover:!bg-[#1B2D7C] !text-[#FAF6F0] shadow-none transition-colors"
                            )
                        )

                    # Contextual Secondary Actions
                    with ui.column().classes(
                        "w-full items-center text-center mt-6 pt-4 border-t border-[#D8CFBF] gap-1.5"
                    ):
                        if is_student:
                            with ui.row().classes(
                                "justify-center items-center text-xs text-[#3A4B7C] gap-1.5 flex-wrap"
                            ):
                                ui.label("Need an account?")
                                ui.link("Register as Student", "/register").classes(
                                    "text-[#0E1D61] font-bold hover:text-[#B89A5A] hover:underline no-underline"
                                )
                            with ui.row().classes(
                                "justify-center items-center text-xs text-[#6B7B9E] gap-1.5 flex-wrap mt-1"
                            ):
                                ui.label("Faculty member?")
                                ui.link("Administrator Sign In", "/admin/login").classes(
                                    "text-[#3A4B7C] font-semibold hover:text-[#0E1D61] hover:underline no-underline"
                                )
                        else:
                            with ui.row().classes(
                                "justify-center items-center text-xs text-[#3A4B7C] gap-1.5 flex-wrap"
                            ):
                                ui.label("Are you a student?")
                                ui.link("Student Sign In", "/student/login").classes(
                                    "text-[#0E1D61] font-bold hover:text-[#B89A5A] hover:underline no-underline"
                                )


def register_auth_pages() -> None:
    """Register all public-facing authentication routes with NiceGUI."""

    @ui.page("/login")
    def login_landing_page() -> None:
        """Primary public landing page and portal selection gateway."""
        if api_client.get_current_user() is not None:
            ui.navigate.to("/dashboard")
            return

        with auth_layout(max_width_class="max-w-6xl", page_type="landing"):
            # 1. Primary Intro & Hero Viewport
            with ui.element("section").classes("w-full py-6 sm:py-10"):
                with ui.column().classes("w-full max-w-3xl gap-4"):
                    # Institutional Badge
                    with ui.row().classes("items-center gap-2"):
                        ui.badge("Academic Knowledge Platform", color="amber-1").props(
                            "text-color=brown-9"
                        ).classes("text-xs font-bold px-2.5 py-1 border border-[#B89A5A]")
                        ui.label("Multi-Format Text RAG System").classes(
                            "text-xs font-semibold text-[#3A4B7C]"
                        )

                    # Primary Value Headline
                    ui.label("Grounded Knowledge Assistant for University Courses").classes(
                        "text-3xl sm:text-4xl lg:text-5xl font-bold text-[#0E1D61] tracking-tight leading-[1.15] font-editorial"
                    )

                    # Concise Supporting Paragraph
                    ui.label(
                        "Ask natural questions across university course syllabi, lecture materials, and academic guidelines. "
                        "Receive precise, evidence-backed answers with verifiable in-browser source citations from official documents."
                    ).classes("text-base sm:text-lg text-[#3A4B7C] leading-relaxed max-w-2xl")

                    # Primary Call to Action Controls
                    with ui.row().classes("items-center gap-3 pt-2 flex-wrap w-full"):
                        ui.button(
                            "Sign in as Student",
                            icon="login",
                            on_click=lambda: ui.navigate.to("/student/login"),
                        ).props("no-caps").classes(
                            "w-full sm:w-auto px-5 py-2.5 font-bold text-sm rounded-md !bg-[#0E1D61] hover:!bg-[#1B2D7C] !text-[#FAF6F0] shadow-none transition-colors"
                        )

                        ui.button(
                            "Administrator Sign In",
                            icon="security",
                            on_click=lambda: ui.navigate.to("/admin/login"),
                        ).props("outline no-caps").classes(
                            "w-full sm:w-auto px-4 py-2.5 font-semibold text-sm rounded-md text-[#0E1D61] border border-[#D8CFBF] hover:bg-[#FAF6F0] transition-colors"
                        )

                        with (
                            ui.link("New student? Register account →", "/register")
                            .classes(
                                "text-xs sm:text-sm font-semibold text-[#0E1D61] hover:text-[#B89A5A] hover:underline no-underline px-1 py-1"
                            )
                        ):
                            pass

            # 2. Live Grounded Evidence Demonstration Card (Product Proof)
            with ui.element("section").classes("w-full my-6 box-border"):
                with ui.card().classes(
                    "w-full p-6 sm:p-8 bg-[#FAF6F0] border border-[#D8CFBF] rounded-lg shadow-none box-border"
                ):
                    with ui.row().classes("w-full justify-between items-center mb-4 flex-wrap gap-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("verified", size="18px").classes("text-[#B89A5A]")
                            ui.label("Grounded Retrieval & Citation Architecture").classes(
                                "text-xs font-bold uppercase tracking-wider text-[#3A4B7C]"
                            )
                        ui.badge("Live Workflow Demonstration", color="amber-1").props(
                            "text-color=brown-9"
                        ).classes("text-[11px] font-semibold px-2 py-0.5 border border-[#B89A5A]")

                    # Query Example
                    with ui.element("div").classes(
                        "w-full p-3.5 bg-[#F5F0E8] border border-[#D8CFBF] rounded-md mb-3"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("help_outline", size="16px").classes("text-[#3A4B7C]")
                            ui.label("Student Question:").classes("text-xs font-bold text-[#3A4B7C]")
                        ui.label(
                            '"What is the policy for late assignment submissions in Advanced Algorithms (CS-301)?"'
                        ).classes("text-sm text-[#0E1D61] font-medium mt-1")

                    # Assistant Verified Answer
                    with ui.element("div").classes(
                        "w-full p-4 bg-[#FFFFFF] border border-[#D8CFBF] rounded-md mb-3"
                    ):
                        with ui.row().classes("items-center gap-2 mb-1.5"):
                            with ui.element("div").classes(
                                "w-5 h-5 rounded bg-[#0E1D61] text-[#FAF6F0] flex items-center justify-center font-bold text-[10px]"
                            ):
                                ui.label("A")
                            ui.label("Assistant Response with Inline Evidence Attribution").classes(
                                "text-xs font-bold text-[#0E1D61]"
                            )
                        ui.label(
                            "Late submissions are accepted up to 72 hours following the deadline with a 10% penalty per 24-hour period. "
                            "Submissions past three calendar days receive zero credit unless supported by an authorized medical exemption [1]."
                        ).classes("text-sm text-[#0E1D61] leading-relaxed")

                    # Grounded Citation Card
                    with ui.element("div").classes(
                        "w-full p-3.5 bg-[#F3EBDD] border border-[#B89A5A] rounded-md"
                    ):
                        with ui.row().classes("items-center justify-between gap-2 flex-wrap"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("description", size="16px").classes("text-[#B89A5A]")
                                ui.label("[1] CS301_Syllabus_Fall2026.pdf").classes(
                                    "text-xs font-bold text-[#0E1D61] font-mono"
                                )
                                ui.label("• Page 4, Section 3.2 Evaluation Policies").classes(
                                    "text-xs text-[#3A4B7C] font-medium"
                                )
                            ui.badge("Verified Grounding", color="green-1").props(
                                "text-color=green-9"
                            ).classes("text-[10px] font-bold px-2 py-0.5 border border-[#2B580C]")

                        ui.label(
                            '"Section 3.2 Late Work: Submissions delayed past the deadline are subject to a 10% deduction per 24-hour period for up to three calendar days. Beyond this window, unsubmitted coursework will receive no marks."'
                        ).classes("text-xs text-[#3A4B7C] italic mt-2 pl-3 border-l-2 border-[#B89A5A] leading-relaxed")

            # 3. Product Value Pillars (Four Core Capabilities)
            with ui.element("section").classes("w-full my-8 box-border"):
                with ui.column().classes("w-full gap-2 mb-6"):
                    ui.label("Engineered for Academic Precision").classes(
                        "text-2xl sm:text-3xl font-bold text-[#0E1D61] tracking-tight font-editorial"
                    )
                    ui.label(
                        "Four foundational principles guarantee factual accuracy, course isolation, and institutional governance."
                    ).classes("text-sm text-[#3A4B7C] leading-relaxed")

                with ui.element("div").classes(
                    "w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 box-border"
                ):
                    pillars = [
                        (
                            "lock",
                            "Course-Scoped Access",
                            "Active published courses are accessible to students with server-side authorization. Zero private course leakage.",
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
                            "w-full p-5 bg-[#FAF6F0] border border-[#D8CFBF] rounded-lg shadow-none flex flex-col justify-between box-border"
                        ):
                            with ui.column().classes("gap-2.5"):
                                with ui.element("div").classes(
                                    "w-9 h-9 rounded-md bg-[#F3EBDD] text-[#0E1D61] border border-[#B89A5A] flex items-center justify-center"
                                ):
                                    ui.icon(icon, size="20px")
                                ui.label(title).classes("text-sm font-bold text-[#0E1D61]")
                                ui.label(desc).classes("text-xs text-[#3A4B7C] leading-relaxed")

            # 4. User Journey Selection (Student vs Administrator Gateways)
            with ui.element("section").classes("w-full my-8 box-border"):
                with ui.column().classes("w-full gap-1 mb-6 text-center items-center"):
                    ui.label("Select Your University Gateway").classes(
                        "text-2xl sm:text-3xl font-bold text-[#0E1D61] tracking-tight font-editorial"
                    )
                    ui.label(
                        "Tailored workflows designed specifically for student learning and academic administration."
                    ).classes("text-sm text-[#3A4B7C] max-w-lg leading-relaxed")

                with ui.element("div").classes(
                    "w-full grid grid-cols-1 lg:grid-cols-2 gap-6 box-border"
                ):
                    # Student Portal Card
                    with ui.card().classes(
                        "w-full p-6 sm:p-8 bg-[#FAF6F0] border border-[#D8CFBF] rounded-lg shadow-none hover:border-[#B89A5A] transition-colors flex flex-col justify-between box-border"
                    ):
                        with ui.column().classes("w-full gap-4"):
                            with ui.row().classes("w-full justify-between items-center"):
                                with ui.element("div").classes(
                                    "w-10 h-10 rounded-md bg-[#0E1D61] text-[#B89A5A] flex items-center justify-center font-bold"
                                ):
                                    ui.icon("school", size="22px")
                                ui.badge("Student Access", color="amber-1").props(
                                    "text-color=brown-9"
                                ).classes("text-[10px] font-bold px-2 py-0.5 border border-[#B89A5A]")

                            with ui.column().classes("gap-1"):
                                ui.label("Student Portal").classes(
                                    "text-xl font-bold text-[#0E1D61] tracking-tight font-editorial"
                                )
                                ui.label(
                                    "Inquire across university courses, research syllabus topics, and verify citations."
                                ).classes("text-xs sm:text-sm text-[#3A4B7C] leading-relaxed")

                            with ui.column().classes("w-full gap-2 pt-2"):
                                student_bullets = [
                                    "Query across all your courses in one conversational workspace",
                                    "Inspect exact document page numbers and text evidence in-browser",
                                    "Zero hallucination safeguards: unverified claims are rejected",
                                ]
                                for bullet in student_bullets:
                                    with ui.row().classes("items-start gap-2"):
                                        ui.icon("check_circle", size="14px").classes("text-[#B89A5A] mt-0.5")
                                        ui.label(bullet).classes("text-xs text-[#3A4B7C] leading-relaxed")

                        with ui.column().classes("w-full mt-6 gap-2.5"):
                            ui.button(
                                "Student Sign In",
                                icon="login",
                                on_click=lambda: ui.navigate.to("/student/login"),
                            ).props("no-caps").classes(
                                "w-full py-2.5 font-bold text-sm rounded-md !bg-[#0E1D61] hover:!bg-[#1B2D7C] !text-[#FAF6F0] shadow-none transition-colors"
                            )
                            with ui.row().classes("w-full justify-center text-xs text-[#3A4B7C] gap-1.5"):
                                ui.label("Need a student account?")
                                ui.link("Register as Student", "/register").classes(
                                    "text-[#0E1D61] font-bold hover:text-[#B89A5A] hover:underline no-underline"
                                )

                    # Administrator Portal Card
                    with ui.card().classes(
                        "w-full p-6 sm:p-8 bg-[#FAF6F0] border border-[#D8CFBF] rounded-lg shadow-none hover:border-[#B89A5A] transition-colors flex flex-col justify-between box-border"
                    ):
                        with ui.column().classes("w-full gap-4"):
                            with ui.row().classes("w-full justify-between items-center"):
                                with ui.element("div").classes(
                                    "w-10 h-10 rounded-md bg-[#0E1D61] text-[#FAF6F0] flex items-center justify-center font-bold"
                                ):
                                    ui.icon("admin_panel_settings", size="22px")
                                ui.badge("Staff Only", color="amber-1").props(
                                    "text-color=brown-9"
                                ).classes("text-[10px] font-bold px-2 py-0.5 border border-[#B89A5A]")

                            with ui.column().classes("gap-1"):
                                ui.label("Administrator Portal").classes(
                                    "text-xl font-bold text-[#0E1D61] tracking-tight font-editorial"
                                )
                                ui.label(
                                    "Curate university courses, upload & chunk documents, monitor vector indexing, and manage access."
                                ).classes("text-xs sm:text-sm text-[#3A4B7C] leading-relaxed")

                            with ui.column().classes("w-full gap-2 pt-2"):
                                admin_bullets = [
                                    "Provision course knowledge bases and configure access permissions",
                                    "Manage multi-format document lifecycles and toggle active retrieval",
                                    "Monitor vector indexing jobs, chunk validation, and telemetry diagnostics",
                                ]
                                for bullet in admin_bullets:
                                    with ui.row().classes("items-start gap-2"):
                                        ui.icon("check_circle", size="14px").classes("text-[#B89A5A] mt-0.5")
                                        ui.label(bullet).classes("text-xs text-[#3A4B7C] leading-relaxed")

                        with ui.column().classes("w-full mt-6 gap-2.5"):
                            ui.button(
                                "Administrator Sign In",
                                icon="security",
                                on_click=lambda: ui.navigate.to("/admin/login"),
                            ).props("no-caps").classes(
                                "w-full py-2.5 font-bold text-sm rounded-md !bg-[#0E1D61] hover:!bg-[#1B2D7C] !text-[#FAF6F0] shadow-none transition-colors"
                            )
                            ui.label("Accounts are provisioned by university administration.").classes(
                                "text-xs text-[#6B7B9E] text-center"
                            )

            # 5. Academic Trust & Security Banner
            with ui.element("section").classes("w-full my-8 box-border"):
                with ui.card().classes(
                    "w-full p-6 sm:p-8 bg-[#0E1D61] text-[#FAF6F0] rounded-lg shadow-none box-border"
                ):
                    with ui.row().classes("w-full justify-between items-start gap-6 flex-wrap"):
                        with ui.column().classes("max-w-xl gap-2"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("shield", size="20px").classes("text-[#B89A5A]")
                                ui.label("Institutional Trust & Privacy Standards").classes(
                                    "text-lg font-bold text-[#FAF6F0] tracking-tight font-editorial"
                                )
                            ui.label(
                                "RAG Assistant operates strictly on university-controlled infrastructure. "
                                "Student inquiries are strictly isolated, and generated responses "
                                "are deterministically bounded to retrieved document evidence."
                            ).classes("text-xs sm:text-sm text-[#FAF6F0]/85 leading-relaxed")

                        with ui.column().classes("gap-2 text-xs text-[#FAF6F0]/85"):
                            ui.label("✓ Argon2id Secure Password Hashing").classes("font-medium")
                            ui.label("✓ HttpOnly Session Cookie Protection").classes("font-medium")
                            ui.label("✓ Multi-Format Text Verification").classes("font-medium")
                            ui.label("✓ Server-Side Course Authorization").classes("font-medium")

            # 6. Bottom Call to Action
            with ui.element("section").classes(
                "w-full py-8 text-center items-center flex flex-col justify-center gap-3 box-border"
            ):
                ui.label("Ready to Study with Verified Citations?").classes(
                    "text-xl sm:text-2xl font-bold text-[#0E1D61] tracking-tight font-editorial"
                )
                ui.label(
                    "Access your course materials or sign in with your student credentials."
                ).classes("text-xs sm:text-sm text-[#3A4B7C] max-w-md")

                with ui.row().classes("items-center justify-center gap-3 mt-2 flex-wrap"):
                    ui.button(
                        "Sign in as Student",
                        icon="school",
                        on_click=lambda: ui.navigate.to("/student/login"),
                    ).props("no-caps").classes(
                        "px-5 py-2.5 font-bold text-xs sm:text-sm rounded-md !bg-[#0E1D61] hover:!bg-[#1B2D7C] !text-[#FAF6F0] shadow-none"
                    )

                    ui.button(
                        "Create Student Account",
                        icon="person_add",
                        on_click=lambda: ui.navigate.to("/register"),
                    ).props("outline no-caps").classes(
                        "px-4 py-2 font-semibold text-xs sm:text-sm rounded-md text-[#0E1D61] border border-[#D8CFBF] hover:bg-[#FAF6F0]"
                    )

                    ui.button(
                        "Administrator Access",
                        icon="admin_panel_settings",
                        on_click=lambda: ui.navigate.to("/admin/login"),
                    ).props("flat no-caps").classes(
                        "px-3 py-2 text-xs sm:text-sm font-medium text-[#3A4B7C] hover:text-[#0E1D61]"
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
                            "w-7 h-7 rounded-md bg-[#0E1D61] text-[#B89A5A] flex items-center justify-center font-bold"
                        ):
                            ui.icon("school", size="16px")
                        ui.label("STUDENT ONBOARDING").classes(
                            "text-xs font-bold uppercase tracking-wider text-[#3A4B7C]"
                        )

                    ui.label("Create your university student account.").classes(
                        "text-2xl sm:text-3xl font-bold text-[#0E1D61] tracking-tight leading-tight font-editorial"
                    )

                    ui.label(
                        "Register with your university email address to access your course materials, research syllabi, and receive verified answers with page citations."
                    ).classes("text-sm sm:text-base text-[#3A4B7C] leading-relaxed")

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
                                "Immediate Course Access",
                                "Active published course knowledge bases are available immediately upon sign in.",
                            ),
                        ]
                        for icon, title, desc in guidelines:
                            with ui.row().classes("items-start gap-3"):
                                with ui.element("div").classes(
                                    "w-7 h-7 rounded-md bg-[#F3EBDD] text-[#0E1D61] border border-[#B89A5A] flex items-center justify-center shrink-0 mt-0.5"
                                ):
                                    ui.icon(icon, size="16px")
                                with ui.column().classes("gap-0"):
                                    ui.label(title).classes("text-xs font-bold text-[#0E1D61]")
                                    ui.label(desc).classes("text-xs text-[#3A4B7C] leading-relaxed")

                    # Already Registered Link
                    with ui.row().classes("items-center gap-1.5 pt-2 text-xs text-[#3A4B7C]"):
                        ui.label("Already have an account?")
                        ui.link("Sign in to Student Portal →", "/student/login").classes(
                            "text-[#0E1D61] font-bold hover:text-[#B89A5A] hover:underline no-underline"
                        )

                # Right Column: Registration Card
                with ui.column().classes("order-1 lg:order-2 lg:col-span-6 w-full"):
                    with ui.card().classes(
                        "w-full max-w-[460px] mx-auto p-6 sm:p-8 bg-[#FAF6F0] border border-[#D8CFBF] rounded-lg shadow-none box-border overflow-hidden"
                    ):
                        with ui.row().classes("w-full justify-between items-center mb-4"):
                            with (
                                ui.link(target="/login")
                                .classes(
                                    "inline-flex items-center gap-1.5 text-xs font-semibold text-[#3A4B7C] hover:text-[#0E1D61] transition-colors no-underline py-1 px-2 -ml-2 rounded-md hover:bg-[#F5F0E8]"
                                )
                                .props('aria-label="Back to home"')
                            ):
                                ui.icon("arrow_back", size="14px").classes("text-[#0E1D61]")
                                ui.label("Back to home").classes("text-xs font-medium")

                            ui.badge("Registration", color="amber-1").props("text-color=brown-9").classes(
                                "text-[10px] font-bold px-2 py-0.5 border border-[#B89A5A]"
                            )

                        with ui.column().classes("w-full gap-1 mb-5"):
                            ui.label("Create Student Account").classes(
                                "text-xl sm:text-2xl font-bold text-[#0E1D61] tracking-tight font-editorial"
                            )
                            ui.label(
                                "Enter your full name and university credentials to register."
                            ).classes("text-xs sm:text-sm text-[#3A4B7C] leading-relaxed")

                        error_container = ui.column().classes("w-full mb-3")

                        # Accessible Form Fields
                        with ui.column().classes("w-full gap-1.5 mb-3.5"):
                            ui.label("Full Name").classes(
                                "text-xs font-semibold uppercase tracking-wider text-[#3A4B7C]"
                            )
                            name_input = (
                                ui.input(placeholder="Student Name")
                                .props("outlined dense")
                                .classes("w-full minimalist-input")
                            )

                        with ui.column().classes("w-full gap-1.5 mb-3.5"):
                            ui.label("University Email").classes(
                                "text-xs font-semibold uppercase tracking-wider text-[#3A4B7C]"
                            )
                            email_input = (
                                ui.input(placeholder="student@university.edu")
                                .props("outlined dense type=email")
                                .classes("w-full minimalist-input")
                            )

                        with ui.column().classes("w-full gap-1.5 mb-5"):
                            ui.label("Password").classes(
                                "text-xs font-semibold uppercase tracking-wider text-[#3A4B7C]"
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
                                "text-[11px] text-[#6B7B9E] mt-0.5"
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
                                    "w-full py-2.5 font-bold text-sm rounded-md !bg-[#0E1D61] hover:!bg-[#1B2D7C] !text-[#FAF6F0] shadow-none transition-colors"
                                )
                            )

                        with ui.column().classes(
                            "w-full items-center text-center mt-5 pt-4 border-t border-[#D8CFBF] gap-1.5"
                        ):
                            with ui.row().classes(
                                "justify-center items-center text-xs text-[#3A4B7C] gap-1.5 flex-wrap"
                            ):
                                ui.label("Already have an account?")
                                ui.link("Student Sign In", "/student/login").classes(
                                    "text-[#0E1D61] font-bold hover:text-[#B89A5A] hover:underline no-underline"
                                )
                            with ui.row().classes(
                                "justify-center items-center text-xs text-[#6B7B9E] gap-1.5 flex-wrap mt-1"
                            ):
                                ui.label("Faculty or staff?")
                                ui.link("Administrator Sign In", "/admin/login").classes(
                                    "text-[#3A4B7C] font-semibold hover:text-[#0E1D61] hover:underline no-underline"
                                )
