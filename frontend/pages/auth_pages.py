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
                        render_alert(str(err), "negative")
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
        """Portal selection entry screen presenting Student vs Administrator portals."""
        if api_client.get_current_user() is not None:
            ui.navigate.to("/dashboard")
            return

        with auth_layout(max_width_class="max-w-5xl"):
            with ui.column().classes("w-full max-w-full items-center"):
                # Institutional Branding Header
                with ui.column().classes("w-full gap-1.5 text-center items-center mb-8"):
                    ui.label("University RAG Assistant").classes(
                        "text-2xl sm:text-3xl font-bold tracking-tight text-slate-900"
                    )
                    ui.label("Academic Knowledge Platform").classes(
                        "text-sm font-medium text-slate-500"
                    )
                    ui.label(
                        "Choose your portal to access course materials or manage university knowledge resources."
                    ).classes("text-xs sm:text-sm text-slate-600 max-w-lg mt-1 leading-relaxed")

                # Two Distinct Portal Cards Side-by-Side
                with ui.element("div").classes(
                    "w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-6 box-border"
                ):
                    # Portal 1: Student Portal
                    with ui.card().classes(
                        "w-full p-6 sm:p-7 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-blue-300 hover:shadow-sm transition-all flex flex-col justify-between box-border"
                    ):
                        with ui.column().classes("w-full gap-3"):
                            with ui.row().classes("w-full justify-between items-center"):
                                with ui.element("div").classes(
                                    "w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center text-blue-700"
                                ):
                                    ui.icon("school", size="18px")
                                ui.label("For students").classes(
                                    "text-xs font-semibold uppercase tracking-wider text-slate-500"
                                )

                            with ui.column().classes("gap-1"):
                                ui.label("Student Portal").classes(
                                    "text-xl font-bold text-slate-900 tracking-tight"
                                )
                                ui.label(
                                    "Access your enrolled course material and ask questions with cited answers."
                                ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                        with ui.column().classes("w-full mt-6"):
                            ui.button(
                                "Student Sign In",
                                icon="login",
                                on_click=lambda: ui.navigate.to("/student/login"),
                            ).props("no-caps").classes(
                                "w-full py-2.5 font-medium text-sm rounded-lg !bg-blue-700 hover:!bg-blue-800 !text-white shadow-xs transition-colors"
                            )

                    # Portal 2: Administrator Portal
                    with ui.card().classes(
                        "w-full p-6 sm:p-7 bg-white border border-slate-200 rounded-xl shadow-xs hover:border-slate-400 hover:shadow-sm transition-all flex flex-col justify-between box-border"
                    ):
                        with ui.column().classes("w-full gap-3"):
                            with ui.row().classes("w-full justify-between items-center"):
                                with ui.element("div").classes(
                                    "w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center text-slate-700"
                                ):
                                    ui.icon("admin_panel_settings", size="18px")
                                ui.label("Authorized personnel").classes(
                                    "text-xs font-semibold uppercase tracking-wider text-slate-500"
                                )

                            with ui.column().classes("gap-1"):
                                ui.label("Administrator Portal").classes(
                                    "text-xl font-bold text-slate-900 tracking-tight"
                                )
                                ui.label(
                                    "Manage courses, documents, vector indexing, and administrative RAG testing."
                                ).classes("text-xs sm:text-sm text-slate-600 leading-relaxed")

                        with ui.column().classes("w-full mt-6"):
                            ui.button(
                                "Administrator Sign In",
                                icon="security",
                                on_click=lambda: ui.navigate.to("/admin/login"),
                            ).props("no-caps").classes(
                                "w-full py-2.5 font-medium text-sm rounded-lg !bg-slate-800 hover:!bg-slate-900 !text-white shadow-xs transition-colors"
                            )

                # Public Student Registration & Administration Notice
                with ui.card().classes(
                    "w-full max-w-4xl p-5 bg-white border border-slate-200 rounded-xl shadow-xs mt-6 box-border"
                ):
                    with ui.row().classes("w-full justify-between items-center flex-wrap gap-4"):
                        with ui.column().classes("gap-0.5"):
                            ui.label("Need a student account?").classes(
                                "text-sm font-semibold text-slate-800"
                            )
                            ui.label(
                                "Create an account to access enrolled university course materials."
                            ).classes("text-xs text-slate-500")
                        ui.button(
                            "Create Student Account",
                            icon="person_add",
                            on_click=lambda: ui.navigate.to("/register"),
                        ).props("outline no-caps").classes(
                            "text-xs font-medium px-4 py-2 border-slate-300 text-slate-700 hover:bg-slate-50 rounded-lg transition-colors"
                        )

                ui.label("Administrator accounts are provisioned internally.").classes(
                    "text-xs text-slate-400 text-center mt-3"
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
                            render_alert(str(err), "negative")
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
