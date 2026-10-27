"""Public Entry and Authentication Presentation Pages.

Redesigned for the Editorial Academic / Field Atlas design system.
Minimalist, high-contrast, focused layouts without generic SaaS cards.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.client.error_handler import normalize_error
from frontend.components.layout import _handle_logout, auth_layout
from frontend.components.ui_kit import render_alert


def _get_safe_return_destination(return_to: str | None, is_student: bool) -> str:
    """Validate internal relative return route and provide role-aware default."""
    default_dest = "/chat" if is_student else "/dashboard"
    if not return_to or not isinstance(return_to, str):
        return default_dest

    clean_return = return_to.strip()
    if (
        not clean_return.startswith("/")
        or clean_return.startswith("//")
        or clean_return.startswith("/\\")
    ):
        return default_dest

    base_path = clean_return.split("?")[0].rstrip("/")
    allowed_routes = {
        "/chat",
        "/knowledge-bases",
        "/profile",
        "/reader",
        "/documents",
        "/indexing",
        "/dashboard",
    }
    if base_path not in allowed_routes:
        return default_dest

    # If student requested /dashboard, resolve directly to /chat
    if base_path == "/dashboard" and is_student:
        return "/chat"

    return clean_return


def _render_authenticated_notice(current_role: str, user_email: str, target_portal: str) -> None:
    """Render structured guidance when an authenticated user visits the opposite role portal."""
    is_student_user = current_role == "STUDENT"
    with auth_layout(max_width_class="max-w-xl", page_type=target_portal):
        with ui.column().classes("w-full py-16 items-center text-center gap-4"):
            with ui.element("div").classes(
                "w-16 h-16 rounded-full bg-gold-light text-primary-navy border border-gold flex items-center justify-center mb-4"
            ):
                ui.icon("info", size="2rem")

            ui.label("Account Role Conflict").classes(
                "text-3xl font-bold text-primary-navy tracking-tight font-editorial"
            )
            ui.label(
                f"You are currently signed in as a {current_role.title()} ({user_email}). "
                f"The {target_portal.title()} Portal requires {target_portal.lower()} privileges."
            ).classes("text-base text-secondary-navy max-w-md leading-relaxed")

            with ui.column().classes("w-full max-w-xs gap-3 mt-8 mx-auto"):
                ui.button(
                    "Go to Workspace" if is_student_user else "Go to Your Dashboard",
                    icon="chat" if is_student_user else "dashboard",
                    on_click=lambda: ui.navigate.to("/chat" if is_student_user else "/dashboard"),
                ).props("no-caps").classes(
                    "w-full py-3 font-semibold text-sm rounded bg-surface-navy hover:bg-opacity-90 text-inverted shadow-none transition-colors"
                )

                ui.button(
                    "Sign Out of Current Account",
                    icon="logout",
                    on_click=_handle_logout,
                ).props("outline no-caps").classes(
                    "w-full py-3 font-semibold text-sm text-primary-navy border border-subtle rounded hover:bg-surface"
                )


def _render_login_form(portal: str, allowed_role: str, return_to: str | None = None) -> None:
    """Render an elegant, editorial two-column login interface."""
    try:
        current_user = api_client.get_current_user()
        if current_user is not None:
            if current_user.role == allowed_role:
                ui.navigate.to("/chat" if current_user.role == "STUDENT" else "/dashboard")
                return
            _render_authenticated_notice(
                current_role=current_user.role,
                user_email=current_user.email,
                target_portal=portal,
            )
            return
    except Exception as e:
        import logging
        logging.error(f"Database unavailable: {e}")

    is_student = allowed_role == "STUDENT"

    with auth_layout(max_width_class="max-w-5xl", page_type=portal):
        with ui.element("div").classes("auth-split-grid my-2 sm:my-4 md:my-6 box-border"):
            # Left side: Editorial Context
            with ui.column().classes("w-full gap-5 sm:gap-6"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon(
                        "school" if is_student else "admin_panel_settings", size="1.25rem"
                    ).classes("text-gold")
                    ui.label(
                        "STUDENT GATEWAY" if is_student else "FACULTY & ADMINISTRATION"
                    ).classes("text-xs font-bold uppercase tracking-widest text-secondary-navy font-mono")

                ui.label(
                    "Access your course materials."
                    if is_student
                    else "Academic content governance."
                ).classes(
                    "text-3xl sm:text-4xl lg:text-5xl font-bold text-primary-navy tracking-tight leading-tight font-editorial"
                )

                ui.label(
                    "Sign in to inquire across your syllabus, lecture slides, and academic guidelines with verified in-browser citations."
                    if is_student
                    else "Authorized administration portal for faculty members to curate course materials, inspect vector embeddings, and manage access."
                ).classes(
                    "text-base lg:text-lg text-secondary-navy leading-relaxed border-l-2 border-gold pl-4 my-1 sm:my-2"
                )

                with ui.column().classes("gap-3 pt-2 text-sm text-secondary-navy"):
                    if is_student:
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", size="16px").classes("text-gold shrink-0")
                            ui.label("Automatic access to all active, published courses")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", size="16px").classes("text-gold shrink-0")
                            ui.label("Inline citations linked directly to source documents")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", size="16px").classes("text-gold shrink-0")
                            ui.label("Native PDF & document reading in-browser")
                    else:
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", size="16px").classes("text-gold shrink-0")
                            ui.label("Strict server-side course isolation & RBAC")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", size="16px").classes("text-gold shrink-0")
                            ui.label("Multi-format text ingestion & vector indexing")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", size="16px").classes("text-gold shrink-0")
                            ui.label("Real-time telemetry and audit activity logs")

            # Right side: Focused Auth Form
            with ui.column().classes("w-full"):
                with ui.card().classes(
                    "w-full p-6 sm:p-8 md:p-10 bg-surface-elevated border border-subtle rounded-lg shadow-sm box-border"
                ):
                    ui.label("Sign In").classes(
                        "text-2xl font-bold text-primary-navy tracking-tight font-editorial mb-6"
                    )

                    error_container = ui.column().classes("w-full mb-4")

                    with ui.column().classes("w-full gap-2 mb-4"):
                        ui.label("Institutional Email").classes(
                            "text-xs font-semibold uppercase tracking-wider text-secondary-navy"
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

                    with ui.column().classes("w-full gap-2 mb-8"):
                        ui.label("Password").classes(
                            "text-xs font-semibold uppercase tracking-wider text-secondary-navy"
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
                                render_alert(
                                    "Please enter a valid institutional email address.", "warning"
                                )
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

                            ui.notify(f"Welcome, {user.full_name}.", type="positive")
                            dest = _get_safe_return_destination(return_to, is_student=is_student)
                            ui.navigate.to(dest)
                        except ValueError as err:
                            with error_container:
                                render_alert(normalize_error(err, context="auth"), "negative")
                        finally:
                            submit_btn.props(remove="loading disable")
                            submit_btn.text = "Sign in"

                    email_input.on("keydown.enter", handle_submit)
                    password_input.on("keydown.enter", handle_submit)

                    submit_btn = (
                        ui.button("Sign in", icon="login", on_click=handle_submit)
                        .props("no-caps")
                        .classes(
                            "w-full py-3 font-bold text-sm rounded bg-surface-navy hover:bg-opacity-90 text-inverted shadow-none transition-colors mb-6"
                        )
                    )

                    with ui.row().classes("w-full justify-center border-t border-subtle pt-6"):
                        if is_student:
                            ui.label("Need a student account?").classes(
                                "text-sm text-secondary-navy"
                            )
                            ui.link("Register here", "/register").classes(
                                "text-sm font-bold text-primary-navy hover:text-gold no-underline"
                            )
                        else:
                            ui.label("Student?").classes("text-sm text-secondary-navy")
                            ui.link("Student Gateway", "/student/login").classes(
                                "text-sm font-bold text-primary-navy hover:text-gold no-underline"
                            )


def register_auth_pages() -> None:
    """Register all public-facing authentication routes with NiceGUI."""

    @ui.page("/login")
    def login_landing_page() -> None:
        """Primary public landing page with rich editorial front cover layout."""
        try:
            current_user = api_client.get_current_user()
            if current_user is not None:
                ui.navigate.to("/chat" if current_user.role == "STUDENT" else "/dashboard")
                return
        except Exception as e:
            import logging
            logging.error(f"Database unavailable: {e}")

        with auth_layout(max_width_class="max-w-6xl", page_type="landing"):
            # 1. Masthead / Hero Section (Open Editorial)
            with ui.column().classes("w-full items-center text-center mt-6 md:mt-12 mb-12 box-border"):
                with ui.row().classes("items-center justify-center gap-2 mb-4"):
                    ui.element("span").classes("w-1.5 h-1.5 rounded-full bg-gold shrink-0")
                    ui.label("AN INSTITUTIONAL ACADEMIC ATLAS · MULTI-FORMAT TEXT RAG").classes(
                        "text-xs font-bold tracking-widest text-primary-navy uppercase font-mono"
                    )
                    ui.element("span").classes("w-1.5 h-1.5 rounded-full bg-gold shrink-0")

                ui.label("Academic Knowledge,\nGrounded in Evidence.").classes(
                    "text-4xl md:text-6xl lg:text-7xl font-bold text-primary-navy tracking-tight leading-[1.08] font-editorial mb-6 whitespace-pre-line"
                )

                ui.label(
                    "Inquire directly across university course syllabi, lecture readings, and academic policies with verifiable in-browser citations. Every answer is synthesized strictly from authorized institutional documents with zero ungrounded speculation."
                ).classes("text-base md:text-lg text-secondary-navy max-w-2xl leading-relaxed mb-8 mx-auto")

                with ui.row().classes("items-center justify-center gap-4 w-full flex-wrap mb-4"):
                    ui.button(
                        "Student Portal",
                        icon="school",
                        on_click=lambda: ui.navigate.to("/student/login"),
                    ).props("no-caps").classes(
                        "px-8 py-3.5 font-bold text-base rounded bg-surface-navy hover:bg-opacity-90 text-inverted shadow-none transition-colors border border-gold"
                    )

                    ui.button(
                        "Faculty Administration",
                        icon="admin_panel_settings",
                        on_click=lambda: ui.navigate.to("/admin/login"),
                    ).props("outline no-caps").classes(
                        "px-8 py-3.5 font-bold text-base rounded text-primary-navy border border-subtle hover:bg-surface"
                    )

                with ui.row().classes("items-center justify-center gap-2 text-sm text-secondary-navy"):
                    ui.label("New student?")
                    ui.link("Register your academic account →", "/register").classes(
                        "font-bold text-primary-navy hover:text-gold no-underline transition-colors"
                    )

            # 2. Live Evidence Grounding Specimen (Open Editorial Surface)
            with ui.column().classes("w-full items-center text-center mt-8 mb-6 box-border"):
                ui.label("THE CITATION STANDARD").classes(
                    "text-xs font-bold uppercase tracking-widest text-secondary-navy font-mono mb-2"
                )
                ui.label("How Grounded Retrieval Works").classes(
                    "text-2xl md:text-3xl font-bold text-primary-navy font-editorial"
                )
                ui.label(
                    "Responses are synthesized strictly from authorized course documents, anchored to specific page numbers for immediate in-browser verification."
                ).classes("text-sm text-secondary-navy max-w-xl text-center mt-2 leading-relaxed")

            with ui.element("div").classes(
                "w-full bg-surface-elevated border border-delicate rounded-lg p-6 sm:p-8 md:p-10 mb-16 shadow-sm border-t-2 border-gold box-border"
            ):
                with ui.row().classes("w-full justify-between items-center pb-4 border-b border-subtle flex-wrap gap-2 text-xs font-mono"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("verified", size="18px").classes("text-gold")
                        ui.label("ARCHIVAL SPECIMEN · CS-301 ADVANCED ALGORITHMS").classes(
                            "font-bold text-primary-navy uppercase tracking-wider"
                        )
                    ui.label("COURSE SYLLABUS · FALL 2026").classes("text-secondary-navy font-semibold uppercase tracking-wider")

                with ui.column().classes("w-full gap-1 pt-6 pb-4"):
                    ui.label("STUDENT INQUIRY").classes(
                        "text-xs font-mono font-bold text-secondary-navy uppercase tracking-wider"
                    )
                    ui.label('“What is the policy for late assignment submissions in Advanced Algorithms?”').classes(
                        "text-base md:text-lg font-semibold text-primary-navy leading-snug"
                    )

                with ui.column().classes("w-full gap-1 py-4 border-l-2 border-gold pl-5 my-2"):
                    ui.label("SYNTHESIZED GROUNDED ANSWER").classes(
                        "text-xs font-mono font-bold text-secondary-navy uppercase tracking-wider"
                    )
                    ui.label(
                        "Late submissions are accepted up to 72 hours following the scheduled deadline with a 10% deduction per 24-hour period. Submissions past three calendar days receive zero credit unless supported by an authorized medical exemption [1]."
                    ).classes("text-base md:text-lg text-primary-navy leading-relaxed")

                with ui.row().classes("w-full justify-between items-center pt-5 mt-4 border-t border-subtle flex-wrap gap-3"):
                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        with ui.element("span").classes(
                            "px-2.5 py-0.5 rounded bg-gold-light border border-gold/40 text-primary-navy font-mono text-xs font-bold"
                        ):
                            ui.label("[1]")
                        ui.label("CS301_Syllabus_Fall2026.pdf").classes(
                            "font-mono text-xs md:text-sm font-bold text-primary-navy"
                        )
                        ui.label("·").classes("text-secondary-navy font-bold")
                        ui.label("Page 4, § 3.2 Evaluation Policies").classes(
                            "text-xs text-secondary-navy font-medium"
                        )
                    with ui.row().classes("items-center gap-1.5 text-[11px] font-mono font-bold text-secondary-navy bg-canvas px-3 py-1 rounded border border-subtle tracking-wider uppercase"):
                        ui.icon("check_circle", size="14px").classes("text-gold")
                        ui.label("Verified In-Browser Citation")

            # 3. Two Dedicated Gateways (Balanced Two-Column Grid)
            with ui.column().classes("w-full items-center text-center mb-8 box-border"):
                ui.label("ACCESS GATEWAYS").classes(
                    "text-xs font-bold uppercase tracking-widest text-secondary-navy font-mono mb-2"
                )
                ui.label("Dedicated Institutional Portals").classes(
                    "text-2xl md:text-3xl font-bold text-primary-navy font-editorial"
                )
                ui.label(
                    "Select your institutional role to enter the dedicated academic workspace."
                ).classes("text-sm text-secondary-navy max-w-xl text-center mt-2 leading-relaxed")

            with ui.element("div").classes("w-full grid grid-cols-1 md:grid-cols-2 gap-8 mb-16 items-stretch"):
                # Student Gateway Panel
                with ui.column().classes(
                    "w-full h-full p-8 md:p-10 bg-surface-elevated border border-delicate rounded-lg justify-between gap-8 border-t-2 border-gold shadow-sm box-border"
                ):
                    with ui.column().classes("gap-6 w-full"):
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.icon("school", size="2rem").classes("text-gold")
                            ui.label("STUDENT ACCESS").classes(
                                "text-[11px] font-bold uppercase tracking-wider text-secondary-navy bg-canvas px-2.5 py-1 rounded border border-subtle font-mono"
                            )

                        with ui.column().classes("gap-2"):
                            ui.label("Student Portal").classes("text-2xl md:text-3xl font-bold text-primary-navy font-editorial")
                            ui.label(
                                "Inquire across active course syllabi, research readings, and verify claims with exact page citations in-browser."
                            ).classes("text-sm text-secondary-navy leading-relaxed")

                        with ui.column().classes("gap-3 pt-2 text-sm text-secondary-navy"):
                            with ui.row().classes("items-start gap-2.5"):
                                ui.icon("check_circle", size="16px").classes("text-gold mt-0.5 shrink-0")
                                ui.label("Automatic access to all active, student-visible courses").classes("leading-snug")
                            with ui.row().classes("items-start gap-2.5"):
                                ui.icon("check_circle", size="16px").classes("text-gold mt-0.5 shrink-0")
                                ui.label("Inspect exact page numbers and evidence excerpts in-browser").classes("leading-snug")
                            with ui.row().classes("items-start gap-2.5"):
                                ui.icon("check_circle", size="16px").classes("text-gold mt-0.5 shrink-0")
                                ui.label("Zero hallucination safeguards: unverified claims rejected").classes("leading-snug")

                    with ui.column().classes("w-full gap-3 pt-4 border-t border-subtle"):
                        ui.button(
                            "Enter Student Portal",
                            icon="login",
                            on_click=lambda: ui.navigate.to("/student/login"),
                        ).props("no-caps").classes(
                            "w-full py-3.5 font-bold text-sm rounded bg-surface-navy hover:bg-opacity-90 text-inverted shadow-none transition-colors border border-gold"
                        )
                        with ui.row().classes("items-center justify-center gap-1.5 text-xs text-secondary-navy w-full"):
                            ui.label("Need an account?")
                            ui.link("Register student account →", "/register").classes(
                                "font-bold text-primary-navy hover:text-gold no-underline transition-colors"
                            )

                # Administrator Gateway Panel
                with ui.column().classes(
                    "w-full h-full p-8 md:p-10 bg-surface border border-delicate rounded-lg justify-between gap-8 border-t-2 border-secondary-navy shadow-sm box-border"
                ):
                    with ui.column().classes("gap-6 w-full"):
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.icon("admin_panel_settings", size="2rem").classes("text-primary-navy")
                            ui.label("FACULTY & STAFF").classes(
                                "text-[11px] font-bold uppercase tracking-wider text-secondary-navy bg-canvas px-2.5 py-1 rounded border border-subtle font-mono"
                            )

                        with ui.column().classes("gap-2"):
                            ui.label("Administrator Portal").classes("text-2xl md:text-3xl font-bold text-primary-navy font-editorial")
                            ui.label(
                                "Curate university courses, upload and chunk documents, monitor vector indexing pipelines, and manage access."
                            ).classes("text-sm text-secondary-navy leading-relaxed")

                        with ui.column().classes("gap-3 pt-2 text-sm text-secondary-navy"):
                            with ui.row().classes("items-start gap-2.5"):
                                ui.icon("check_circle", size="16px").classes("text-secondary-navy mt-0.5 shrink-0")
                                ui.label("Multi-format document lifecycles: PDF, DOCX, TXT, MD, CSV").classes("leading-snug")
                            with ui.row().classes("items-start gap-2.5"):
                                ui.icon("check_circle", size="16px").classes("text-secondary-navy mt-0.5 shrink-0")
                                ui.label("Monitor vector indexing jobs, chunk validation, and telemetry").classes("leading-snug")
                            with ui.row().classes("items-start gap-2.5"):
                                ui.icon("check_circle", size="16px").classes("text-secondary-navy mt-0.5 shrink-0")
                                ui.label("Strict server-side course isolation & granular admin permissions").classes("leading-snug")

                    with ui.column().classes("w-full gap-3 pt-4 border-t border-subtle"):
                        ui.button(
                            "Enter Administrator Portal",
                            icon="admin_panel_settings",
                            on_click=lambda: ui.navigate.to("/admin/login"),
                        ).props("outline no-caps").classes(
                            "w-full py-3.5 font-bold text-sm rounded text-primary-navy border border-primary-navy hover:bg-surface-elevated transition-colors"
                        )
                        ui.label("Authorized university faculty, staff, and administrators").classes(
                            "text-xs text-secondary-navy text-center w-full font-medium"
                        )

            # 4. Institutional Architecture Pillars (Open 4-Column Grid)
            with ui.column().classes("w-full pt-10 pb-4 border-t border-subtle"):
                with ui.element("div").classes("w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6"):
                    with ui.column().classes("gap-1.5"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("verified_user", size="18px").classes("text-gold")
                            ui.label("Server-Side RBAC").classes("text-xs font-bold font-mono uppercase tracking-wider text-primary-navy")
                        ui.label("Role-based query filtering and course visibility enforced at database level.").classes(
                            "text-xs text-secondary-navy leading-normal"
                        )

                    with ui.column().classes("gap-1.5"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("lock", size="18px").classes("text-gold")
                            ui.label("Zero Token URL Leakage").classes("text-xs font-bold font-mono uppercase tracking-wider text-primary-navy")
                        ui.label("Same-origin HttpOnly session cookies; credentials never exposed in URLs or scripts.").classes(
                            "text-xs text-secondary-navy leading-normal"
                        )

                    with ui.column().classes("gap-1.5"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("find_in_page", size="18px").classes("text-gold")
                            ui.label("Native Document Viewer").classes("text-xs font-bold font-mono uppercase tracking-wider text-primary-navy")
                        ui.label("Direct in-browser PDF rendering with page fragment jumps and citation drawer.").classes(
                            "text-xs text-secondary-navy leading-normal"
                        )

                    with ui.column().classes("gap-1.5"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("dataset", size="18px").classes("text-gold")
                            ui.label("Multi-Format Text RAG").classes("text-xs font-bold font-mono uppercase tracking-wider text-primary-navy")
                        ui.label("Full-text extraction, chunking, and hybrid retrieval across PDF, DOCX, TXT, MD, CSV.").classes(
                            "text-xs text-secondary-navy leading-normal"
                        )

    @ui.page("/student/login")
    def student_login_page(return_to: str | None = None) -> None:
        """Dedicated Student Portal sign-in screen."""
        _render_login_form(portal="student", allowed_role="STUDENT", return_to=return_to)

    @ui.page("/admin/login")
    def admin_login_page(return_to: str | None = None) -> None:
        """Dedicated Administrator Portal sign-in screen."""
        _render_login_form(portal="admin", allowed_role="ADMIN", return_to=return_to)

    @ui.page("/register")
    def register_page() -> None:
        """Student registration page with balanced two-column layout."""
        try:
            current_user = api_client.get_current_user()
            if current_user is not None:
                ui.navigate.to("/chat" if current_user.role == "STUDENT" else "/dashboard")
                return
        except Exception as e:
            import logging
            logging.error(f"Database unavailable: {e}")

        with auth_layout(max_width_class="max-w-5xl", page_type="register"):
            with ui.element("div").classes("auth-split-grid my-2 sm:my-4 md:my-6 box-border"):
                # Left side: Registration Context
                with ui.column().classes("w-full gap-5 sm:gap-6"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("person_add", size="1.25rem").classes("text-gold")
                        ui.label("STUDENT ENROLLMENT").classes(
                            "text-xs font-bold uppercase tracking-widest text-secondary-navy font-mono"
                        )

                    ui.label("Join the academic workspace.").classes(
                        "text-3xl sm:text-4xl lg:text-5xl font-bold text-primary-navy tracking-tight leading-tight font-editorial"
                    )

                    ui.label(
                        "Register with your university email address to access your active courses immediately with verified citations."
                    ).classes(
                        "text-base lg:text-lg text-secondary-navy leading-relaxed border-l-2 border-gold pl-4 my-1 sm:my-2"
                    )

                    with ui.column().classes("gap-3 pt-2 text-sm text-secondary-navy"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", size="16px").classes("text-gold shrink-0")
                            ui.label("Automatic access to all published active courses")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", size="16px").classes("text-gold shrink-0")
                            ui.label("Zero manual enrollment delays for student-visible courses")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", size="16px").classes("text-gold shrink-0")
                            ui.label("Interactive questions grounded in syllabus files")

                    with ui.row().classes("items-center gap-2 mt-4"):
                        ui.label("Already have an account?").classes("text-sm text-secondary-navy")
                        ui.link("Sign in here →", "/student/login").classes(
                            "text-sm font-bold text-primary-navy hover:text-gold no-underline"
                        )

                # Right side: Registration Form
                with ui.column().classes("w-full"):
                    with ui.card().classes(
                        "w-full p-6 sm:p-8 md:p-10 bg-surface-elevated border border-subtle rounded-lg shadow-sm box-border"
                    ):
                        ui.label("Create Account").classes(
                            "text-2xl font-bold text-primary-navy tracking-tight font-editorial mb-6"
                        )

                        error_container = ui.column().classes("w-full mb-4")

                        with ui.column().classes("w-full gap-2 mb-4"):
                            ui.label("Full Name").classes(
                                "text-xs font-semibold uppercase tracking-wider text-secondary-navy"
                            )
                            name_input = (
                                ui.input(placeholder="Student Name")
                                .props("outlined dense")
                                .classes("w-full minimalist-input")
                            )

                        with ui.column().classes("w-full gap-2 mb-4"):
                            ui.label("Institutional Email").classes(
                                "text-xs font-semibold uppercase tracking-wider text-secondary-navy"
                            )
                            email_input = (
                                ui.input(placeholder="student@university.edu")
                                .props("outlined dense type=email")
                                .classes("w-full minimalist-input")
                            )

                        with ui.column().classes("w-full gap-2 mb-8"):
                            ui.label("Password").classes(
                                "text-xs font-semibold uppercase tracking-wider text-secondary-navy"
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

                        def handle_register() -> None:
                            error_container.clear()
                            name = (name_input.value or "").strip()
                            email = (email_input.value or "").strip()
                            password = password_input.value or ""

                            if not name:
                                with error_container:
                                    render_alert("Full name is required.", "warning")
                                return
                            if not email or "@" not in email:
                                with error_container:
                                    render_alert("Institutional email is required.", "warning")
                                return
                            if not password or len(password) < 8:
                                with error_container:
                                    render_alert(
                                        "Password must be at least 8 characters.", "warning"
                                    )
                                return

                            submit_btn.props("loading disable")
                            submit_btn.text = "Creating Account..."

                            try:
                                user = api_client.student_register(
                                    full_name=name, email=email, password=password
                                )
                                ui.notify(
                                    f"Welcome, {user.full_name}! Registration successful.",
                                    type="positive",
                                )
                                ui.navigate.to("/chat")
                            except ValueError as err:
                                with error_container:
                                    render_alert(normalize_error(err, context="auth"), "negative")
                            finally:
                                submit_btn.props(remove="loading disable")
                                submit_btn.text = "Create Account"

                        name_input.on("keydown.enter", handle_register)
                        email_input.on("keydown.enter", handle_register)
                        password_input.on("keydown.enter", handle_register)

                        submit_btn = (
                            ui.button("Create Account", icon="person_add", on_click=handle_register)
                            .props("no-caps")
                            .classes(
                                "w-full py-3 font-bold text-sm rounded bg-surface-navy hover:bg-opacity-90 text-inverted shadow-none transition-colors"
                            )
                        )
