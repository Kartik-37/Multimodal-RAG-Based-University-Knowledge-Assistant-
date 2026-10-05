"""
Authentication Presentation Pages with Accessible Form Controls and Role Separation.

Provides the public authentication experience:
- /login: Polished entry page offering distinct Student and Administrator portal choices.
- /student/login: Dedicated Student Portal authentication.
- /admin/login: Dedicated Administrator Portal authentication with institutional security notice.
- /register: Student registration strictly creating STUDENT accounts.

Adheres to WCAG 2.1 AA keyboard accessibility, visible labeling, restrained institutional
aesthetics, and strict server-side role enforcement.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.components.layout import _handle_logout, auth_layout
from frontend.components.ui_kit import render_alert


def _render_back_to_portals(target: str = "/login") -> None:
    """Render a subtle, accessible institutional back-navigation control."""
    with ui.row().classes("w-full justify-start mb-4"):
        with (
            ui.link(target=target)
            .classes(
                "inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors no-underline py-1 px-2 -ml-2 rounded-md hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-blue-600"
            )
            .props('aria-label="Back to portals"')
        ):
            ui.icon("arrow_back", size="14px").classes("text-slate-500 group-hover:text-slate-800")
            ui.label("Back to portals").classes("text-xs font-medium")


def _render_authenticated_role_notice(
    current_role: str, user_email: str, target_portal: str
) -> None:
    """Render explicit guidance when an already-authenticated user visits the wrong portal."""
    with auth_layout(max_width_class="max-w-md"):
        with ui.card().classes(
            "w-full max-w-[440px] mx-auto p-6 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-xs text-center items-center my-auto box-border"
        ):
            with ui.element("div").classes(
                "w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center mb-3"
            ):
                ui.icon("info", size="24px").classes("text-blue-700")
            ui.label("Already Signed In").classes("text-xl font-bold text-slate-900 tracking-tight")
            ui.label(
                f"You are currently signed in as an {current_role.title()} ({user_email}). "
                f"The {target_portal.title()} Portal is intended for {target_portal.lower()} accounts."
            ).classes("text-xs sm:text-sm text-slate-600 max-w-sm mt-2 leading-relaxed")

            with ui.column().classes("w-full gap-2.5 mt-6"):
                ui.button(
                    "Go to Dashboard",
                    icon="dashboard",
                    on_click=lambda: ui.navigate.to("/dashboard"),
                ).props("no-caps").classes(
                    "w-full py-2.5 font-medium text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs transition-colors"
                )

                ui.button(
                    "Sign Out",
                    icon="logout",
                    on_click=_handle_logout,
                ).props("outline no-caps").classes(
                    "w-full py-2.5 font-medium text-sm text-slate-700 border-slate-300 rounded-lg hover:bg-slate-50"
                )


def _render_login_form(portal: str, allowed_role: str) -> None:
    """
    Reusable login form component parameterized for Student vs Administrator portals.

    :param portal: 'student' or 'admin'
    :param allowed_role: 'STUDENT' or 'ADMIN'
    """
    current_user = api_client.get_current_user()
    if current_user is not None:
        if current_user.role == allowed_role:
            ui.navigate.to("/dashboard")
            return
        else:
            _render_authenticated_role_notice(
                current_role=current_role_val,
                user_email=current_user.email,
                target_portal=portal,
            ) if (current_role_val := current_user.role) else None
            return

    is_student = allowed_role == "STUDENT"

    with auth_layout(max_width_class="max-w-md"):
        with ui.card().classes(
            "w-full max-w-[440px] mx-auto p-5 sm:p-7 bg-white border border-slate-200 rounded-xl shadow-xs my-auto box-border"
        ):
            # Subtle back-navigation control
            _render_back_to_portals("/login")

            # Header with unified academic identity and role context
            with ui.column().classes("w-full gap-0.5 mb-5"):
                with ui.row().classes("items-center gap-1.5 mb-1"):
                    ui.icon("school", size="15px").classes(
                        "text-blue-700" if is_student else "text-slate-600"
                    )
                    ui.label("University RAG Assistant").classes(
                        "text-xs font-semibold uppercase tracking-wider text-slate-500"
                    )

                ui.label("Student Portal" if is_student else "Administrator Portal").classes(
                    "text-xl sm:text-2xl font-bold text-slate-900 tracking-tight"
                )

                ui.label(
                    "Sign in to access your enrolled course materials."
                    if is_student
                    else "Authorized administrators can manage university knowledge resources."
                ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed mt-0.5")

            # Inline error alert container
            error_container = ui.column().classes("w-full mb-3")

            # Accessible Form Fields with Explicit Labels
            with ui.column().classes("w-full gap-1 mb-3.5"):
                ui.label("Email Address").classes("text-xs font-semibold text-slate-700")
                email_input = (
                    ui.input(
                        placeholder="student@university.edu"
                        if is_student
                        else "admin@university.edu"
                    )
                    .props("outlined dense type=email")
                    .classes("w-full")
                )

            with ui.column().classes("w-full gap-1 mb-5"):
                ui.label("Password").classes("text-xs font-semibold text-slate-700")
                password_input = (
                    ui.input(
                        placeholder="••••••••",
                        password=True,
                        password_toggle_button=True,
                    )
                    .props("outlined dense")
                    .classes("w-full")
                )

            def handle_submit() -> None:
                error_container.clear()
                email = (email_input.value or "").strip()
                password = password_input.value or ""

                if not email or not password:
                    with error_container:
                        render_alert("Please provide both email address and password.", "warning")
                    return

                submit_btn.props("loading disable")
                submit_btn.text = "Signing in..."
                try:
                    user = api_client.login(email, password, required_role=allowed_role)
                    ui.notify(f"Welcome, {user.full_name}!", type="positive")
                    ui.navigate.to("/dashboard")
                except ValueError as err:
                    with error_container:
                        render_alert(normalize_error(err, context="auth"), "negative")
                finally:
                    submit_btn.props(remove="loading disable")
                    submit_btn.text = "Student Sign In" if is_student else "Administrator Sign In"

            # Keyboard accessibility: Enter key triggers submission
            email_input.on("keydown.enter", handle_submit)
            password_input.on("keydown.enter", handle_submit)

            with ui.column().classes("w-full gap-2.5"):
                if is_student:
                    submit_btn = (
                        ui.button(
                            "Student Sign In",
                            icon="login",
                            on_click=handle_submit,
                        )
                        .props("no-caps")
                        .classes(
                            "w-full py-2.5 font-medium text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs transition-colors"
                        )
                    )
                else:
                    submit_btn = (
                        ui.button(
                            "Administrator Sign In",
                            icon="security",
                            on_click=handle_submit,
                        )
                        .props("no-caps")
                        .classes(
                            "w-full py-2.5 font-medium text-sm rounded-lg !bg-slate-800 hover:!bg-slate-900 !text-white shadow-xs transition-colors"
                        )
                    )

            # Footer navigation
            with ui.column().classes(
                "w-full items-center text-center mt-5 pt-4 border-t border-slate-100 gap-1.5"
            ):
                if is_student:
                    with ui.row().classes(
                        "justify-center items-center text-xs text-slate-500 gap-1 flex-wrap"
                    ):
                        ui.label("Don't have a student account?")
                        ui.link("Create Student Account", "/register").classes(
                            "text-blue-700 font-semibold hover:underline no-underline"
                        )
                else:
                    ui.label("Administrator accounts are provisioned internally.").classes(
                        "text-xs text-slate-400"
                    )


def register_auth_pages() -> None:
    """Register authentication presentation routes with NiceGUI."""

    @ui.page("/login")
    def login_portal_selection_page() -> None:
        """Professional academic entrance portal presenting Student and Administrator gateways."""
        if api_client.get_current_user() is not None:
            ui.navigate.to("/dashboard")
            return

        # ----------------------------------------------------------------------
        # Modal: Explore Public Knowledge Base Materials
        # ----------------------------------------------------------------------
        with (
            ui.dialog() as materials_dialog,
            ui.card().classes(
                "w-full max-w-2xl p-6 sm:p-8 bg-white border border-slate-200 rounded-2xl shadow-xl box-border"
            ),
        ):
            with ui.row().classes("w-full justify-between items-start mb-4"):
                with ui.row().classes("items-center gap-2.5"):
                    with ui.element("div").classes(
                        "w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center text-blue-700"
                    ):
                        ui.icon("menu_book", size="22px")
                    with ui.column().classes("gap-0.5"):
                        ui.label("University Course & Knowledge Catalog").classes(
                            "text-lg font-bold text-slate-900 tracking-tight"
                        )
                        ui.label(
                            "Public overview of indexed academic curricula and resources"
                        ).classes("text-xs text-slate-500")
                ui.button(icon="close", on_click=materials_dialog.close).props(
                    "flat round dense"
                ).classes("text-slate-400 hover:text-slate-700")

            with ui.column().classes("w-full gap-4 my-2"):
                # Course 1
                with ui.card().classes(
                    "w-full p-4 bg-slate-50/80 border border-slate-200 rounded-xl"
                ):
                    with ui.row().classes("w-full justify-between items-center mb-1"):
                        ui.label("BCA-301: Computer Architecture").classes(
                            "text-sm font-bold text-slate-800"
                        )
                        ui.badge("1024-d Vectors", color="blue-8").classes("text-[10px] px-2")
                    ui.label(
                        "Processor micro-architecture, memory hierarchy, cache coherence, pipelining, and assembly interfaces."
                    ).classes("text-xs text-slate-600 leading-relaxed mb-2")
                    with ui.row().classes(
                        "items-center gap-3 text-[11px] text-slate-500 font-medium"
                    ):
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("description", size="13px").classes("text-slate-400")
                            ui.label("KSU-Act-English.pdf (33 Chunks)")
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("check_circle", size="13px").classes("text-emerald-600")
                            ui.label("Status: Active & Verified")

                # Course 2
                with ui.card().classes(
                    "w-full p-4 bg-slate-50/80 border border-slate-200 rounded-xl"
                ):
                    with ui.row().classes("w-full justify-between items-center mb-1"):
                        ui.label("Official University Regulations & Statutes").classes(
                            "text-sm font-bold text-slate-800"
                        )
                        ui.badge("Syllabus & Policy", color="slate-7").classes("text-[10px] px-2")
                    ui.label(
                        "Institutional academic statutes, degree ordinances, examination criteria, and university grading policies."
                    ).classes("text-xs text-slate-600 leading-relaxed mb-2")
                    with ui.row().classes(
                        "items-center gap-3 text-[11px] text-slate-500 font-medium"
                    ):
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("verified", size="13px").classes("text-blue-600")
                            ui.label("Institutional Authority")
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("check_circle", size="13px").classes("text-emerald-600")
                            ui.label("Status: Active & Verified")

                # Course 3
                with ui.card().classes(
                    "w-full p-4 bg-slate-50/80 border border-slate-200 rounded-xl"
                ):
                    with ui.row().classes("w-full justify-between items-center mb-1"):
                        ui.label("BCA Curriculum & Foundations").classes(
                            "text-sm font-bold text-slate-800"
                        )
                        ui.badge("Undergraduate", color="indigo-8").classes("text-[10px] px-2")
                    ui.label(
                        "Semester course blueprints, syllabus modules, lab practical manuals, and reading references."
                    ).classes("text-xs text-slate-600 leading-relaxed mb-2")
                    with ui.row().classes(
                        "items-center gap-3 text-[11px] text-slate-500 font-medium"
                    ):
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("library_books", size="13px").classes("text-indigo-500")
                            ui.label("Semester Syllabus Modules")

            with ui.row().classes(
                "w-full justify-between items-center pt-4 border-t border-slate-100 mt-2"
            ):
                ui.label(
                    "Sign in with student credentials to ask questions across these materials."
                ).classes("text-xs text-slate-500")
                with ui.row().classes("gap-2"):
                    ui.button("Close", on_click=materials_dialog.close).props(
                        "flat no-caps"
                    ).classes("text-xs text-slate-600")
                    ui.button(
                        "Student Sign In",
                        icon="login",
                        on_click=lambda: ui.navigate.to("/student/login"),
                    ).props("no-caps").classes(
                        "text-xs !bg-blue-700 hover:!bg-blue-800 !text-white px-4 py-2 rounded-lg"
                    )

        with auth_layout(max_width_class="max-w-6xl"):
            with ui.column().classes("w-full max-w-full items-center"):
                # --------------------------------------------------------------
                # TOP HERO SECTION: Academic Knowledge Assistant
                # --------------------------------------------------------------
                with ui.column().classes("w-full items-center text-center pt-2 pb-6 max-w-3xl"):
                    # Institutional Trust Pill
                    with ui.element("div").classes(
                        "inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-800 text-xs font-semibold mb-4 tracking-wide"
                    ):
                        ui.icon("school", size="14px").classes("text-blue-700")
                        ui.label("Institutional Academic Intelligence • RAG Architecture")

                    # Hero Primary Heading
                    ui.label("Academic Knowledge Assistant").classes(
                        "text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 leading-tight"
                    )

                    # Hero Subtitle / Product Value Description
                    ui.label(
                        "Semantic inquiry across verified university course materials, lecture notes, and official regulations. "
                        "Ask natural questions and receive precise, evidence-backed answers with strict source citation verification."
                    ).classes(
                        "text-sm sm:text-base text-slate-600 max-w-2xl leading-relaxed mt-3.5 mb-6"
                    )

                    # Primary Hero Quick-Action Row
                    with ui.row().classes("items-center justify-center gap-3 flex-wrap mb-4"):
                        ui.button(
                            "Student Portal",
                            icon="school",
                            on_click=lambda: ui.navigate.to("/student/login"),
                        ).props("no-caps").classes(
                            "px-5 py-2.5 font-medium text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs transition-all"
                        )

                        ui.button(
                            "Administrator Staff",
                            icon="security",
                            on_click=lambda: ui.navigate.to("/admin/login"),
                        ).props("no-caps").classes(
                            "px-5 py-2.5 font-medium text-sm rounded-lg !bg-slate-800 hover:!bg-slate-900 !text-white shadow-xs transition-all"
                        )

                        ui.button(
                            "Explore Public Materials",
                            icon="menu_book",
                            on_click=materials_dialog.open,
                        ).props("outline no-caps").classes(
                            "px-4 py-2.5 font-medium text-sm rounded-lg border-slate-300 text-slate-700 hover:bg-slate-50 transition-all"
                        )

                # --------------------------------------------------------------
                # CAPABILITY HIGHLIGHTS STRIP
                # --------------------------------------------------------------
                with ui.element("div").classes(
                    "w-full max-w-5xl grid grid-cols-1 sm:grid-cols-3 gap-4 my-4 box-border"
                ):
                    # Capability 1
                    with ui.card().classes(
                        "p-4 bg-white border border-slate-200/90 rounded-xl shadow-2xs hover:border-blue-200 transition-colors"
                    ):
                        with ui.row().classes("items-center gap-2.5 mb-1.5"):
                            with ui.element("div").classes(
                                "w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center text-blue-700"
                            ):
                                ui.icon("search", size="18px")
                            ui.label("Hybrid Search").classes("text-sm font-bold text-slate-800")
                        ui.label(
                            "1024-d dense vector embeddings fused with PostgreSQL full-text search via Reciprocal Rank Fusion."
                        ).classes("text-xs text-slate-500 leading-relaxed")

                    # Capability 2
                    with ui.card().classes(
                        "p-4 bg-white border border-slate-200/90 rounded-xl shadow-2xs hover:border-indigo-200 transition-colors"
                    ):
                        with ui.row().classes("items-center gap-2.5 mb-1.5"):
                            with ui.element("div").classes(
                                "w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-700"
                            ):
                                ui.icon("fact_check", size="18px")
                            ui.label("Grounded Citations").classes(
                                "text-sm font-bold text-slate-800"
                            )
                        ui.label(
                            "Direct page, paragraph, and section references. No hallucinations: unverifiable assertions are refused."
                        ).classes("text-xs text-slate-500 leading-relaxed")

                    # Capability 3
                    with ui.card().classes(
                        "p-4 bg-white border border-slate-200/90 rounded-xl shadow-2xs hover:border-slate-300 transition-colors"
                    ):
                        with ui.row().classes("items-center gap-2.5 mb-1.5"):
                            with ui.element("div").classes(
                                "w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-700"
                            ):
                                ui.icon("verified_user", size="18px")
                            ui.label("Institutional Security").classes(
                                "text-sm font-bold text-slate-800"
                            )
                        ui.label(
                            "Argon2id authentication, strict course enrollment isolation, and server-side RBAC permissions."
                        ).classes("text-xs text-slate-500 leading-relaxed")

                # --------------------------------------------------------------
                # TWO-COLUMN PORTAL GATEWAYS
                # --------------------------------------------------------------
                with ui.element("div").classes(
                    "w-full max-w-5xl grid grid-cols-1 md:grid-cols-2 gap-6 my-6 box-border"
                ):
                    # Portal 1: Student Portal Card
                    with ui.card().classes(
                        "w-full p-6 sm:p-8 bg-white border border-slate-200 rounded-2xl shadow-xs hover:border-blue-400 hover:shadow-md transition-all flex flex-col justify-between box-border"
                    ):
                        with ui.column().classes("w-full gap-4"):
                            with ui.row().classes("w-full justify-between items-center"):
                                with ui.element("div").classes(
                                    "w-11 h-11 rounded-xl bg-blue-50 flex items-center justify-center text-blue-700"
                                ):
                                    ui.icon("school", size="22px")
                                with ui.element("span").classes(
                                    "px-2.5 py-1 rounded-md bg-blue-50 text-blue-800 text-[11px] font-bold uppercase tracking-wider"
                                ):
                                    ui.label("Student Access")

                            with ui.column().classes("gap-1.5"):
                                ui.label("Student Portal").classes(
                                    "text-xl sm:text-2xl font-bold text-slate-900 tracking-tight"
                                )
                                ui.label(
                                    "Inquire across all your enrolled university courses, research specific syllabus topics, and view verified citations."
                                ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                            with ui.column().classes("w-full gap-2 pt-2 border-t border-slate-100"):
                                for feature in [
                                    "Cross-course semantic inquiry across enrolled materials",
                                    "Precise page, paragraph, and section source citations",
                                    "Interactive evidence panel for source validation",
                                ]:
                                    with ui.row().classes(
                                        "items-center gap-2 text-xs text-slate-700"
                                    ):
                                        ui.icon("check_circle", size="14px").classes(
                                            "text-blue-600 flex-shrink-0"
                                        )
                                        ui.label(feature)

                        with ui.column().classes("w-full mt-6 gap-2"):
                            ui.button(
                                "Student Sign In",
                                icon="login",
                                on_click=lambda: ui.navigate.to("/student/login"),
                            ).props("no-caps").classes(
                                "w-full py-2.5 font-medium text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs transition-colors"
                            )
                            with ui.row().classes(
                                "w-full justify-center text-xs text-slate-500 gap-1 mt-1"
                            ):
                                ui.label("Need an account?")
                                ui.link("Register as Student", "/register").classes(
                                    "text-blue-700 font-semibold hover:underline no-underline"
                                )

                    # Portal 2: Administrator Portal Card
                    with ui.card().classes(
                        "w-full p-6 sm:p-8 bg-white border border-slate-200 rounded-2xl shadow-xs hover:border-slate-400 hover:shadow-md transition-all flex flex-col justify-between box-border"
                    ):
                        with ui.column().classes("w-full gap-4"):
                            with ui.row().classes("w-full justify-between items-center"):
                                with ui.element("div").classes(
                                    "w-11 h-11 rounded-xl bg-slate-100 flex items-center justify-center text-slate-800"
                                ):
                                    ui.icon("admin_panel_settings", size="22px")
                                with ui.element("span").classes(
                                    "px-2.5 py-1 rounded-md bg-slate-100 text-slate-800 text-[11px] font-bold uppercase tracking-wider"
                                ):
                                    ui.label("Authorized Staff")

                            with ui.column().classes("gap-1.5"):
                                ui.label("Administrator Portal").classes(
                                    "text-xl sm:text-2xl font-bold text-slate-900 tracking-tight"
                                )
                                ui.label(
                                    "Curate university courses, upload & chunk documents, monitor pgvector indexing, and audit system performance."
                                ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                            with ui.column().classes("w-full gap-2 pt-2 border-t border-slate-100"):
                                for feature in [
                                    "Document ingestion (PDF, DOCX, TXT) with chunking",
                                    "Vector indexing lifecycle with cardinality verification",
                                    "Administrative diagnostic chat & CrossEncoder inspection",
                                ]:
                                    with ui.row().classes(
                                        "items-center gap-2 text-xs text-slate-700"
                                    ):
                                        ui.icon("check_circle", size="14px").classes(
                                            "text-slate-600 flex-shrink-0"
                                        )
                                        ui.label(feature)

                        with ui.column().classes("w-full mt-6 gap-2"):
                            ui.button(
                                "Administrator Sign In",
                                icon="security",
                                on_click=lambda: ui.navigate.to("/admin/login"),
                            ).props("no-caps").classes(
                                "w-full py-2.5 font-medium text-sm rounded-lg !bg-slate-800 hover:!bg-slate-900 !text-white shadow-xs transition-colors"
                            )
                            ui.label(
                                "Administrator accounts are provisioned internally by IT."
                            ).classes("text-xs text-slate-400 text-center mt-1")

                # --------------------------------------------------------------
                # "HOW IT WORKS" ACADEMIC RAG ARCHITECTURE SECTION
                # --------------------------------------------------------------
                with ui.card().classes(
                    "w-full max-w-5xl p-6 sm:p-8 bg-slate-50 border border-slate-200 rounded-2xl my-6 box-border"
                ):
                    with ui.column().classes("w-full gap-1 mb-6 text-center items-center"):
                        with ui.element("span").classes(
                            "px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-800 text-[10px] font-bold uppercase tracking-wider mb-1"
                        ):
                            ui.label("Architecture & Workflow")
                        ui.label("How the Academic Knowledge Platform Works").classes(
                            "text-xl sm:text-2xl font-bold text-slate-900 tracking-tight"
                        )
                        ui.label(
                            "A deterministic, four-stage RAG pipeline engineered for precision and source attribution"
                        ).classes("text-xs sm:text-sm text-slate-500 max-w-xl")

                    with ui.element("div").classes(
                        "w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
                    ):
                        stages = [
                            (
                                "1",
                                "Document Ingestion",
                                "description",
                                "PDF, DOCX, and TXT files are validated, normalized, and partitioned into token-budgeted chunks with page metadata.",
                            ),
                            (
                                "2",
                                "Vector & Lexical Index",
                                "hub",
                                "Chunks are embedded into 1024-d vectors via Ollama and indexed in PostgreSQL alongside tsvector keyword tables.",
                            ),
                            (
                                "3",
                                "Hybrid RRF & Rerank",
                                "tune",
                                "Queries trigger simultaneous vector and full-text retrieval, fused via RRF and rescored using HuggingFace CrossEncoder.",
                            ),
                            (
                                "4",
                                "Grounded Generation",
                                "format_quote",
                                "Strictly prompt-bounded local LLM generates answers backed by evidence with verifiable [source_X] citations.",
                            ),
                        ]
                        for step_num, title, icon_name, desc in stages:
                            with ui.card().classes(
                                "p-4 bg-white border border-slate-200/80 rounded-xl shadow-2xs flex flex-col justify-between"
                            ):
                                with ui.column().classes("gap-2"):
                                    with ui.row().classes("justify-between items-center w-full"):
                                        with ui.element("div").classes(
                                            "w-7 h-7 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold text-xs"
                                        ):
                                            ui.label(step_num)
                                        ui.icon(icon_name, size="18px").classes("text-slate-400")
                                    ui.label(title).classes("text-sm font-bold text-slate-800")
                                    ui.label(desc).classes(
                                        "text-[11px] text-slate-500 leading-relaxed"
                                    )

                # --------------------------------------------------------------
                # STUDENT REGISTRATION BANNER / CALL TO ACTION
                # --------------------------------------------------------------
                with ui.card().classes(
                    "w-full max-w-5xl p-6 bg-gradient-to-r from-blue-900 to-slate-900 text-white rounded-2xl shadow-sm mb-6 box-border"
                ):
                    with ui.row().classes("w-full justify-between items-center flex-wrap gap-4"):
                        with ui.column().classes("gap-1"):
                            ui.label("Ready to study with verified citations?").classes(
                                "text-lg font-bold text-white tracking-tight"
                            )
                            ui.label(
                                "Register with your student email to access enrolled course documents and study guides."
                            ).classes("text-xs text-blue-200")
                        with ui.row().classes("gap-3 items-center"):
                            ui.button(
                                "Explore Course Catalog",
                                icon="menu_book",
                                on_click=materials_dialog.open,
                            ).props("flat no-caps").classes(
                                "text-xs font-semibold text-white hover:bg-white/10 rounded-lg px-3 py-2"
                            )
                            ui.button(
                                "Create Student Account",
                                icon="person_add",
                                on_click=lambda: ui.navigate.to("/register"),
                            ).props("no-caps").classes(
                                "text-xs font-medium px-4 py-2.5 !bg-blue-600 hover:!bg-blue-500 text-white rounded-lg shadow-xs transition-colors"
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
        """Student registration page strictly provisioning STUDENT role."""
        if api_client.get_current_user() is not None:
            ui.navigate.to("/dashboard")
            return

        with auth_layout(max_width_class="max-w-md"):
            with ui.card().classes(
                "w-full max-w-[440px] mx-auto p-5 sm:p-7 bg-white border border-slate-200 rounded-xl shadow-xs my-auto box-border"
            ):
                _render_back_to_portals("/login")

                with ui.column().classes("w-full gap-0.5 mb-5"):
                    with ui.row().classes("items-center gap-1.5 mb-1"):
                        ui.icon("school", size="15px").classes("text-blue-700")
                        ui.label("University RAG Assistant").classes(
                            "text-xs font-semibold uppercase tracking-wider text-slate-500"
                        )

                    ui.label("Create Student Account").classes(
                        "text-xl sm:text-2xl font-bold text-slate-900 tracking-tight"
                    )
                    ui.label(
                        "Create a student account to access enrolled university course materials."
                    ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed mt-0.5")

                error_container = ui.column().classes("w-full mb-3")

                # Accessible Form Fields
                with ui.column().classes("w-full gap-1 mb-3.5"):
                    ui.label("Full Name").classes("text-xs font-semibold text-slate-700")
                    name_input = (
                        ui.input(placeholder="Student Name")
                        .props("outlined dense")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mb-3.5"):
                    ui.label("Email Address").classes("text-xs font-semibold text-slate-700")
                    email_input = (
                        ui.input(placeholder="student@university.edu")
                        .props("outlined dense type=email")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mb-5"):
                    ui.label("Password").classes("text-xs font-semibold text-slate-700")
                    password_input = (
                        ui.input(
                            placeholder="At least 8 characters",
                            password=True,
                            password_toggle_button=True,
                        )
                        .props("outlined dense")
                        .classes("w-full")
                    )
                    ui.label("Password must be at least 8 characters.").classes(
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
                            render_alert("Please enter a valid email address.", "warning")
                        return

                    if len(password) < 8:
                        with error_container:
                            render_alert("Password must be at least 8 characters.", "warning")
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
                            f"Account registered! Welcome, {user.full_name}!", type="positive"
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
