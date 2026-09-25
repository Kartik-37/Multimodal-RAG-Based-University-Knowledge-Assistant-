"""
Authentication Presentation Pages with Accessible Form Controls and Role Separation.

Provides the public authentication experience:
- /login: Polished entry page offering distinct Student and Administrator portal choices.
- /student/login: Dedicated Student Portal authentication.
- /admin/login: Dedicated Administrator Portal authentication with security notice.
- /register: Student registration strictly creating STUDENT accounts.

Adheres to WCAG 2.1 AA keyboard accessibility, visible labeling, and server-side role enforcement.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import _handle_logout, page_layout
from frontend.components.ui_kit import render_alert


def _render_authenticated_role_notice(
    current_role: str, user_email: str, target_portal: str
) -> None:
    """Render explicit guidance when an already-authenticated user visits the wrong portal."""
    with ui.card().classes(
        "w-full max-w-md mx-auto p-6 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-sm mt-8 text-center items-center"
    ):
        ui.icon("info", size="2.5rem").classes("text-blue-600 mb-2")
        ui.label("Already Signed In").classes("text-xl font-bold text-slate-900 tracking-tight")
        ui.label(
            f"You are currently signed in as an {current_role.title()} ({user_email}). "
            f"The {target_portal.title()} Portal is intended for {target_portal.lower()} accounts."
        ).classes("text-xs text-slate-600 max-w-sm mt-2 leading-relaxed")

        with ui.column().classes("w-full gap-2.5 mt-6"):
            ui.button(
                "Go to Dashboard",
                icon="dashboard",
                on_click=lambda: ui.navigate.to("/dashboard"),
            ).props("color=primary no-caps").classes("w-full py-2 font-medium text-sm rounded-lg")

            ui.button(
                "Sign Out",
                icon="logout",
                on_click=_handle_logout,
            ).props("outline no-caps").classes(
                "w-full py-2 font-medium text-sm text-slate-700 border-slate-300 rounded-lg"
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
            with page_layout(title="", require_auth=False):
                _render_authenticated_role_notice(
                    current_role=current_user.role,
                    user_email=current_user.email,
                    target_portal=portal,
                )
            return

    is_student = allowed_role == "STUDENT"

    with page_layout(title="", require_auth=False):
        with ui.card().classes(
            "w-full max-w-md mx-auto p-6 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-sm mt-6 mb-10"
        ):
            # Back link to portal selection
            with ui.row().classes("w-full mb-3"):
                ui.link("← Back to Portal Selection", "/login").classes(
                    "text-xs font-medium text-slate-500 hover:text-blue-600 transition-colors"
                )

            # Header with portal branding
            with ui.column().classes("w-full gap-1 mb-5 text-center items-center"):
                if is_student:
                    ui.icon("school", size="2.5rem").classes(
                        "text-blue-600 p-2 bg-blue-50 rounded-lg mb-1"
                    )
                    ui.badge("STUDENT PORTAL", color="blue-100", text_color="blue-800").classes(
                        "text-[10px] font-bold tracking-wider uppercase px-2.5 py-0.5 mb-1"
                    )
                    ui.label("Student Portal").classes(
                        "text-2xl font-extrabold text-slate-900 tracking-tight"
                    )
                    ui.label(
                        "Sign in to access your enrolled course materials and ask questions with verified sources."
                    ).classes("text-xs text-slate-600 max-w-sm mt-1 leading-relaxed")
                else:
                    ui.icon("admin_panel_settings", size="2.5rem").classes(
                        "text-slate-800 p-2 bg-slate-100 rounded-lg mb-1"
                    )
                    ui.badge(
                        "ADMINISTRATOR PORTAL", color="amber-100", text_color="amber-800"
                    ).classes("text-[10px] font-bold tracking-wider uppercase px-2.5 py-0.5 mb-1")
                    ui.label("Administrator Portal").classes(
                        "text-2xl font-extrabold text-slate-900 tracking-tight"
                    )
                    ui.label(
                        "Authorized administrators can manage courses, documents, indexing, permissions and RAG testing."
                    ).classes("text-xs text-slate-600 max-w-sm mt-1 leading-relaxed")

            # Inline error alert container
            error_container = ui.column().classes("w-full mb-3")

            # Accessible Form Fields with Explicit Labels
            with ui.column().classes("w-full gap-1 mb-3"):
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
                try:
                    user = api_client.login(email, password, required_role=allowed_role)
                    ui.notify(f"Welcome, {user.full_name}!", type="positive")
                    ui.navigate.to("/dashboard")
                except ValueError as err:
                    with error_container:
                        render_alert(str(err), "negative")
                finally:
                    submit_btn.props(remove="loading disable")

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
                        .props("color=primary no-caps")
                        .classes("w-full py-2.5 font-medium text-sm rounded-lg shadow-xs")
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
                            "w-full py-2.5 font-medium text-sm bg-slate-800 hover:bg-slate-900 text-white rounded-lg shadow-xs"
                        )
                    )

            # Footer navigation
            with ui.column().classes(
                "w-full items-center text-center mt-5 pt-4 border-t border-slate-100 gap-2"
            ):
                if is_student:
                    with ui.row().classes("justify-center text-xs text-slate-500"):
                        ui.label("Don't have a student account?")
                        ui.link("Create Student Account", "/register").classes(
                            "text-blue-600 font-semibold hover:underline ml-1"
                        )
                else:
                    ui.label(
                        "Administrator accounts are provisioned by authorized administrators."
                    ).classes("text-[11px] text-slate-400")


def register_auth_pages() -> None:
    """Register authentication presentation routes with NiceGUI."""

    @ui.page("/login")
    def login_portal_selection_page() -> None:
        """Portal selection entry screen presenting Student vs Administrator portals."""
        if api_client.get_current_user() is not None:
            ui.navigate.to("/dashboard")
            return

        with page_layout(title="", require_auth=False):
            with ui.column().classes("w-full max-w-4xl mx-auto py-6 sm:py-10 px-4 items-center"):
                # Institutional Branding Header
                ui.badge("INSTITUTIONAL KNOWLEDGE PLATFORM", color="blue-900").classes(
                    "text-[10px] sm:text-xs font-semibold tracking-wider uppercase px-3 py-1 mb-2"
                )
                ui.label("University RAG Assistant").classes(
                    "text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight text-center"
                )
                ui.label(
                    "Select your designated institutional portal to access academic course material or administrative controls."
                ).classes(
                    "text-xs sm:text-sm text-slate-600 max-w-xl text-center mt-2 leading-relaxed"
                )

                # Two Distinct Portal Cards
                with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-6 mt-8"):
                    # Portal 1: Student Portal
                    with ui.card().classes(
                        "p-6 sm:p-7 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-blue-300 hover:shadow-md transition-all flex flex-col justify-between"
                    ):
                        with ui.column().classes("w-full gap-2"):
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.icon("school", size="2.5rem").classes(
                                    "text-blue-600 p-2.5 bg-blue-50 rounded-lg"
                                )
                                ui.badge(
                                    "FOR STUDENTS", color="blue-100", text_color="blue-800"
                                ).classes("text-[10px] font-bold tracking-wide")

                            ui.label("Student Portal").classes(
                                "text-xl font-bold text-slate-900 mt-2"
                            )
                            ui.label(
                                "Access enrolled course material and ask academic questions with verified, grounded citations."
                            ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                            with ui.column().classes(
                                "w-full gap-1.5 mt-3 py-2 border-y border-slate-100 text-xs text-slate-600"
                            ):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("check_circle", size="xs").classes("text-blue-600")
                                    ui.label("Search course syllabi & lecture notes")
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("check_circle", size="xs").classes("text-blue-600")
                                    ui.label("Ask questions with grounded citations")
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("check_circle", size="xs").classes("text-blue-600")
                                    ui.label("Global search across all enrolled courses")

                        with ui.column().classes("w-full gap-1.5 mt-6"):
                            ui.button(
                                "Student Sign In",
                                icon="login",
                                on_click=lambda: ui.navigate.to("/student/login"),
                            ).props("color=primary no-caps").classes(
                                "w-full py-2.5 font-semibold text-sm rounded-lg shadow-xs"
                            )
                            ui.label("Institutional student credentials required").classes(
                                "text-[11px] text-slate-400 text-center"
                            )

                    # Portal 2: Administrator Portal
                    with ui.card().classes(
                        "p-6 sm:p-7 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-slate-400 hover:shadow-md transition-all flex flex-col justify-between"
                    ):
                        with ui.column().classes("w-full gap-2"):
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.icon("admin_panel_settings", size="2.5rem").classes(
                                    "text-slate-800 p-2.5 bg-slate-100 rounded-lg"
                                )
                                ui.badge(
                                    "AUTHORIZED PERSONNEL",
                                    color="amber-100",
                                    text_color="amber-800",
                                ).classes("text-[10px] font-bold tracking-wide")

                            ui.label("Administrator Portal").classes(
                                "text-xl font-bold text-slate-900 mt-2"
                            )
                            ui.label(
                                "Manage courses, documents, vector indexing, administrator permissions, and RAG testing."
                            ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                            with ui.column().classes(
                                "w-full gap-1.5 mt-3 py-2 border-y border-slate-100 text-xs text-slate-600"
                            ):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("check_circle", size="xs").classes("text-slate-700")
                                    ui.label("Course lifecycle & document publication gate")
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("check_circle", size="xs").classes("text-slate-700")
                                    ui.label("Background vector embedding & index jobs")
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("check_circle", size="xs").classes("text-slate-700")
                                    ui.label("Scoped admin chat & retrieval diagnostics")

                        with ui.column().classes("w-full gap-1.5 mt-6"):
                            ui.button(
                                "Administrator Sign In",
                                icon="security",
                                on_click=lambda: ui.navigate.to("/admin/login"),
                            ).props("no-caps").classes(
                                "w-full py-2.5 font-semibold text-sm bg-slate-800 hover:bg-slate-900 text-white rounded-lg shadow-xs"
                            )
                            ui.label("Restricted to provisioned university administrators").classes(
                                "text-[11px] text-slate-400 text-center"
                            )

                # Public Student Registration & Administration Notice
                with ui.card().classes(
                    "w-full max-w-4xl p-4 sm:p-5 bg-white border border-slate-200 rounded-xl shadow-xs mt-6"
                ):
                    with ui.row().classes("w-full justify-between items-center gap-4"):
                        with ui.column().classes("gap-0.5"):
                            ui.label("Student account needed?").classes(
                                "text-sm font-semibold text-slate-800"
                            )
                            ui.label(
                                "Register as a student to access your enrolled university course materials."
                            ).classes("text-xs text-slate-500")
                        ui.button(
                            "Create Student Account",
                            icon="person_add",
                            on_click=lambda: ui.navigate.to("/register"),
                        ).props("outline no-caps color=primary").classes(
                            "text-xs font-semibold px-4 py-1.5 rounded-lg"
                        )

                ui.label(
                    "Administrator accounts cannot be registered publicly. They must be provisioned by an existing system administrator."
                ).classes("text-[11px] text-slate-400 text-center mt-3")

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

        with page_layout(title="", require_auth=False):
            with ui.card().classes(
                "w-full max-w-md mx-auto p-6 sm:p-8 bg-white border border-slate-200 rounded-xl shadow-sm mt-6 mb-10"
            ):
                with ui.row().classes("w-full mb-3"):
                    ui.link("← Back to Portal Selection", "/login").classes(
                        "text-xs font-medium text-slate-500 hover:text-blue-600 transition-colors"
                    )

                with ui.column().classes("w-full gap-1 mb-4 text-center items-center"):
                    ui.icon("school", size="2.5rem").classes(
                        "text-blue-600 p-2 bg-blue-50 rounded-lg mb-1"
                    )
                    ui.badge(
                        "STUDENT REGISTRATION", color="blue-100", text_color="blue-800"
                    ).classes("text-[10px] font-bold tracking-wider uppercase px-2.5 py-0.5 mb-1")
                    ui.label("Create Student Account").classes(
                        "text-2xl font-extrabold text-slate-900 tracking-tight"
                    )
                    ui.label(
                        "Register as a student to access your enrolled university course materials."
                    ).classes("text-xs text-slate-600 max-w-sm mt-1 leading-relaxed")

                error_container = ui.column().classes("w-full mb-3")

                # Accessible Form Fields
                with ui.column().classes("w-full gap-1 mb-3"):
                    ui.label("Full Name").classes("text-xs font-semibold text-slate-700")
                    name_input = (
                        ui.input(placeholder="Student Name")
                        .props("outlined dense")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mb-3"):
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
                    ui.label("At least 8 characters.").classes("text-[11px] text-slate-400")

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
                            render_alert(str(err), "negative")
                    finally:
                        reg_btn.props(remove="loading disable")

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
                        .props("color=primary no-caps")
                        .classes("w-full py-2.5 font-medium text-sm rounded-lg shadow-xs")
                    )

                with ui.column().classes(
                    "w-full items-center text-center mt-5 pt-4 border-t border-slate-100 gap-2"
                ):
                    with ui.row().classes("justify-center text-xs text-slate-500"):
                        ui.label("Already have an account?")
                        ui.link("Student Sign In", "/student/login").classes(
                            "text-blue-600 font-semibold hover:underline ml-1"
                        )
