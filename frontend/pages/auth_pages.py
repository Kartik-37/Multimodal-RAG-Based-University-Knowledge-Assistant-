"""
Authentication Presentation Pages with Accessible Form Controls.

Provides sign-in and registration interfaces adhering to WCAG 2.1 AA keyboard
accessibility and visible labeling guidelines. Communicates strictly via FrontendAPIClient.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout
from frontend.components.ui_kit import render_alert


def register_auth_pages() -> None:
    """Register /login and /register routes with NiceGUI."""

    @ui.page("/login")
    def login_page() -> None:
        with page_layout(title="", require_auth=False):
            with ui.card().classes(
                "w-full max-w-md mx-auto p-6 sm:p-8 bg-white border border-slate-200 rounded-lg shadow-sm mt-8"
            ):
                with ui.column().classes("w-full gap-1 mb-6 text-center items-center"):
                    ui.icon("school", size="2.5rem").classes("text-blue-600 mb-1")
                    ui.label("University RAG Assistant").classes(
                        "text-xl font-bold text-slate-900 tracking-tight"
                    )
                    ui.label(
                        "Sign in with your institutional credentials to access knowledge bases."
                    ).classes("text-xs text-slate-500 max-w-xs")

                # Inline error container
                error_container = ui.column().classes("w-full mb-3")

                # Accessible Form Fields with Explicit Labels
                with ui.column().classes("w-full gap-1 mb-3"):
                    ui.label("Email Address").classes("text-xs font-semibold text-slate-700")
                    email_input = (
                        ui.input(placeholder="user@university.edu")
                        .props("outlined dense")
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
                            render_alert(
                                "Please provide both email address and password.", "warning"
                            )
                        return

                    submit_btn.props("loading disable")
                    try:
                        user = api_client.login(email, password)
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
                    submit_btn = (
                        ui.button(
                            "Sign In",
                            icon="login",
                            on_click=handle_submit,
                        )
                        .props("color=primary no-caps")
                        .classes("w-full py-2 font-medium text-sm")
                    )

                with ui.row().classes("w-full justify-center text-xs text-slate-500 mt-5"):
                    ui.label("Don't have an account?")
                    ui.link("Register here", "/register").classes(
                        "text-blue-600 font-semibold hover:underline ml-1"
                    )

    @ui.page("/register")
    def register_page() -> None:
        with page_layout(title="", require_auth=False):
            with ui.card().classes(
                "w-full max-w-md mx-auto p-6 sm:p-8 bg-white border border-slate-200 rounded-lg shadow-sm mt-8"
            ):
                with ui.column().classes("w-full gap-1 mb-4 text-center items-center"):
                    ui.icon("person_add", size="2.5rem").classes("text-blue-600 mb-1")
                    ui.label("Create Student Account").classes(
                        "text-xl font-bold text-slate-900 tracking-tight"
                    )
                    ui.label(
                        "Public registration establishes a student profile with access to enrolled courses."
                    ).classes("text-xs text-slate-500 max-w-xs")

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
                            "Create Account",
                            icon="person_add",
                            on_click=handle_register,
                        )
                        .props("color=primary no-caps")
                        .classes("w-full py-2 font-medium text-sm")
                    )

                with ui.row().classes("w-full justify-center text-xs text-slate-500 mt-5"):
                    ui.label("Already registered?")
                    ui.link("Sign in here", "/login").classes(
                        "text-blue-600 font-semibold hover:underline ml-1"
                    )
