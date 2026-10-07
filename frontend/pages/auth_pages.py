"""
Authentication Presentation Pages with Clean Academic Information Architecture.

Provides the public authentication experience:
- /login: Clean portal selection presenting Student and Administrator gateways.
- /student/login: Dedicated Student Portal authentication.
- /admin/login: Dedicated Administrator Portal authentication with institutional security notice.
- /register: Student registration strictly creating STUDENT accounts.

Adheres to accessible controls, visible labels, restrained academic aesthetics,
and strict server-side role enforcement.
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
            ui.icon("arrow_back", size="14px").classes("text-slate-500")
            ui.label("Back to portal selection").classes("text-xs font-medium")


def _render_authenticated_role_notice(
    current_role: str, user_email: str, target_portal: str
) -> None:
    """Render explicit guidance when an already-authenticated user visits the wrong portal."""
    with auth_layout(max_width_class="max-w-md"):
        with ui.card().classes(
            "w-full max-w-[440px] mx-auto p-6 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-xs text-center items-center my-auto box-border"
        ):
            with ui.element("div").classes(
                "w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center mb-3 text-blue-700"
            ):
                ui.icon("info", size="24px")
            ui.label("Already Signed In").classes("text-xl font-bold text-slate-900 tracking-tight")
            ui.label(
                f"You are currently signed in as {current_role.title()} ({user_email}). "
                f"The {target_portal.title()} Portal is intended for {target_portal.lower()} accounts."
            ).classes("text-xs sm:text-sm text-slate-600 max-w-sm mt-2 leading-relaxed")

            with ui.column().classes("w-full gap-2.5 mt-6"):
                ui.button(
                    "Go to Dashboard",
                    icon="dashboard",
                    on_click=lambda: ui.navigate.to("/dashboard"),
                ).props("no-caps").classes(
                    "w-full py-2.5 font-medium text-sm rounded-lg !bg-slate-900 hover:!bg-slate-800 !text-white shadow-xs transition-colors"
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
                current_role=current_user.role,
                user_email=current_user.email,
                target_portal=portal,
            )
            return

    is_student = allowed_role == "STUDENT"

    with auth_layout(max_width_class="max-w-md"):
        with ui.card().classes(
            "w-full max-w-[440px] mx-auto p-6 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-xs my-auto box-border"
        ):
            # Back-navigation control
            _render_back_to_portals("/login")

            # Header with unified academic identity and role context
            with ui.column().classes("w-full gap-1 mb-6"):
                with ui.row().classes("items-center gap-2 mb-1"):
                    with ui.element("div").classes(
                        "w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center text-slate-700"
                    ):
                        ui.icon("school" if is_student else "admin_panel_settings", size="16px")
                    ui.label("RAG Assistant").classes(
                        "text-xs font-bold uppercase tracking-wider text-slate-500"
                    )

                ui.label("Student Sign In" if is_student else "Administrator Sign In").classes(
                    "text-2xl font-bold text-slate-900 tracking-tight"
                )

                ui.label(
                    "Sign in to access your enrolled course materials and ask questions with verified citations."
                    if is_student
                    else "Sign in to manage university courses, documents, vector indexing, and administrative access."
                ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

            # Inline error alert container
            error_container = ui.column().classes("w-full mb-3")

            # Accessible Form Fields with Explicit Labels
            with ui.column().classes("w-full gap-1.5 mb-4"):
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

            with ui.column().classes("w-full gap-1.5 mb-5"):
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
                btn_bg = "!bg-blue-700 hover:!bg-blue-800" if is_student else "!bg-slate-900 hover:!bg-slate-800"
                submit_btn = (
                    ui.button(
                        "Student Sign In" if is_student else "Administrator Sign In",
                        icon="login" if is_student else "security",
                        on_click=handle_submit,
                    )
                    .props("no-caps")
                    .classes(
                        f"w-full py-2.5 font-medium text-sm rounded-lg {btn_bg} !text-white shadow-xs transition-colors"
                    )
                )

            # Footer navigation
            with ui.column().classes(
                "w-full items-center text-center mt-5 pt-4 border-t border-slate-100 gap-2"
            ):
                if is_student:
                    with ui.row().classes(
                        "justify-center items-center text-xs text-slate-500 gap-1 flex-wrap"
                    ):
                        ui.label("Don't have a student account?")
                        ui.link("Register as Student", "/register").classes(
                            "text-blue-700 font-semibold hover:underline no-underline"
                        )
                    with ui.row().classes(
                        "justify-center items-center text-xs text-slate-400 gap-1 flex-wrap"
                    ):
                        ui.label("Faculty or staff?")
                        ui.link("Administrator Sign In", "/admin/login").classes(
                            "text-slate-600 font-medium hover:underline no-underline"
                        )
                else:
                    ui.label("Institutional security: Server-side RBAC enforced.").classes(
                        "text-[11px] text-slate-400 font-mono"
                    )
                    with ui.row().classes(
                        "justify-center items-center text-xs text-slate-500 gap-1 flex-wrap mt-1"
                    ):
                        ui.label("Looking for Student Portal?")
                        ui.link("Student Sign In", "/student/login").classes(
                            "text-blue-700 font-semibold hover:underline no-underline"
                        )


def register_auth_pages() -> None:
    """Register authentication presentation routes with NiceGUI."""

    @ui.page("/login")
    def login_portal_selection_page() -> None:
        """Clean academic entrance portal presenting Student and Administrator gateways."""
        if api_client.get_current_user() is not None:
            ui.navigate.to("/dashboard")
            return

        with auth_layout(max_width_class="max-w-4xl"):
            with ui.column().classes("w-full items-center text-center pt-4 pb-6"):
                # Institutional Branding Header
                with ui.row().classes("items-center gap-2.5 mb-2"):
                    with ui.element("div").classes(
                        "w-10 h-10 rounded-xl bg-slate-900 text-white flex items-center justify-center font-bold"
                    ):
                        ui.icon("school", size="22px")
                    ui.label("RAG Assistant").classes(
                        "text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900"
                    )

                ui.label(
                    "University Knowledge Assistant — select your portal to continue."
                ).classes("text-sm text-slate-600 max-w-md")

            # Two-Column Portal Selector Grid
            with ui.element("div").classes(
                "w-full grid grid-cols-1 md:grid-cols-2 gap-6 my-2 box-border"
            ):
                # 1. Student Portal Card
                with ui.card().classes(
                    "w-full p-6 sm:p-7 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-blue-400 transition-colors flex flex-col justify-between box-border"
                ):
                    with ui.column().classes("w-full gap-3"):
                        with ui.row().classes("w-full justify-between items-center"):
                            with ui.element("div").classes(
                                "w-10 h-10 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center"
                            ):
                                ui.icon("school", size="22px")
                            ui.badge("Student Access", color="blue-1").props("text-color=blue-9").classes(
                                "text-[10px] font-bold px-2 py-0.5 border border-blue-200"
                            )

                        with ui.column().classes("gap-1"):
                            ui.label("Student Portal").classes(
                                "text-xl font-bold text-slate-900 tracking-tight"
                            )
                            ui.label(
                                "Inquire across enrolled university courses, research syllabus topics, and verify citations."
                            ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                    with ui.column().classes("w-full mt-6 gap-2.5"):
                        ui.button(
                            "Student Sign In",
                            icon="login",
                            on_click=lambda: ui.navigate.to("/student/login"),
                        ).props("no-caps").classes(
                            "w-full py-2.5 font-medium text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs transition-colors"
                        )
                        with ui.row().classes("w-full justify-center text-xs text-slate-500 gap-1"):
                            ui.label("Need an account?")
                            ui.link("Register as Student", "/register").classes(
                                "text-blue-700 font-semibold hover:underline no-underline"
                            )

                # 2. Administrator Portal Card
                with ui.card().classes(
                    "w-full p-6 sm:p-7 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-slate-400 transition-colors flex flex-col justify-between box-border"
                ):
                    with ui.column().classes("w-full gap-3"):
                        with ui.row().classes("w-full justify-between items-center"):
                            with ui.element("div").classes(
                                "w-10 h-10 rounded-lg bg-slate-100 text-slate-800 flex items-center justify-center"
                            ):
                                ui.icon("admin_panel_settings", size="22px")
                            ui.badge("Staff Only", color="slate-2").props("text-color=slate-8").classes(
                                "text-[10px] font-bold px-2 py-0.5 border border-slate-300"
                            )

                        with ui.column().classes("gap-1"):
                            ui.label("Administrator Portal").classes(
                                "text-xl font-bold text-slate-900 tracking-tight"
                            )
                            ui.label(
                                "Curate university courses, upload & chunk documents, monitor vector indexing, and manage access."
                            ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                    with ui.column().classes("w-full mt-6 gap-2.5"):
                        ui.button(
                            "Administrator Sign In",
                            icon="security",
                            on_click=lambda: ui.navigate.to("/admin/login"),
                        ).props("no-caps").classes(
                            "w-full py-2.5 font-medium text-sm rounded-lg !bg-slate-900 hover:!bg-slate-800 !text-white shadow-xs transition-colors"
                        )
                        ui.label(
                            "Accounts are provisioned by university administration."
                        ).classes("text-xs text-slate-400 text-center")

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
                "w-full max-w-[440px] mx-auto p-6 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-xs my-auto box-border"
            ):
                _render_back_to_portals("/login")

                with ui.column().classes("w-full gap-1 mb-6"):
                    with ui.row().classes("items-center gap-2 mb-1"):
                        with ui.element("div").classes(
                            "w-7 h-7 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold"
                        ):
                            ui.icon("school", size="16px")
                        ui.label("RAG Assistant").classes(
                            "text-xs font-bold uppercase tracking-wider text-slate-500"
                        )

                    ui.label("Create Student Account").classes(
                        "text-2xl font-bold text-slate-900 tracking-tight"
                    )
                    ui.label(
                        "Register with your university email to access enrolled course materials."
                    ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                error_container = ui.column().classes("w-full mb-3")

                # Accessible Form Fields
                with ui.column().classes("w-full gap-1.5 mb-3.5"):
                    ui.label("Full Name").classes("text-xs font-semibold text-slate-700")
                    name_input = (
                        ui.input(placeholder="Student Name")
                        .props("outlined dense")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1.5 mb-3.5"):
                    ui.label("University Email").classes("text-xs font-semibold text-slate-700")
                    email_input = (
                        ui.input(placeholder="student@university.edu")
                        .props("outlined dense type=email")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1.5 mb-5"):
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
