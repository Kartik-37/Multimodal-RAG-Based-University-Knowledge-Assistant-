"""
Authentication Presentation Pages.

Provides login and registration forms for the presentation shell.
Communicates strictly via the FrontendAPIClient boundary.
"""

from nicegui import ui

from frontend.client.api_client import api_client
from frontend.components.layout import page_layout


def register_auth_pages() -> None:
    """Register /login and /register routes with NiceGUI."""

    @ui.page("/login")
    def login_page() -> None:
        with page_layout(title="", require_auth=False):
            with ui.card().classes(
                "w-full max-w-md mx-auto p-6 border border-gray-200 shadow-sm mt-8"
            ):
                with ui.column().classes("w-full gap-1 mb-4"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("lock", size="md").classes("text-blue-600")
                        ui.label("Sign In").classes("text-xl font-bold text-gray-900")
                    ui.label("Enter your credentials to access knowledge bases and chat.").classes(
                        "text-xs text-gray-500"
                    )

                email_input = ui.input(
                    label="Email Address",
                    placeholder="user@example.com",
                ).classes("w-full mb-2")

                password_input = ui.input(
                    label="Password",
                    password=True,
                    password_toggle_button=True,
                ).classes("w-full mb-4")

                def handle_submit() -> None:
                    try:
                        email = email_input.value or ""
                        password = password_input.value or ""
                        user = api_client.login(email.strip(), password)
                        ui.notify(f"Welcome back, {user.full_name}!", type="positive")
                        ui.navigate.to("/dashboard")
                    except ValueError as err:
                        ui.notify(str(err), type="negative")

                def handle_demo_login() -> None:
                    email_input.value = "admin@university.edu"
                    password_input.value = "DemoPass123!"
                    handle_submit()

                with ui.column().classes("w-full gap-2"):
                    ui.button("Sign In", icon="login", on_click=handle_submit).props(
                        "color=primary"
                    ).classes("w-full")

                    ui.button(
                        "Quick Sign-In (Demo User)",
                        icon="bolt",
                        on_click=handle_demo_login,
                    ).props("outline color=secondary").classes("w-full text-xs")

                with ui.row().classes("w-full justify-center text-xs text-gray-500 mt-4"):
                    ui.label("Don't have an account?")
                    ui.link("Register here", "/register").classes("text-blue-600 font-semibold")

    @ui.page("/register")
    def register_page() -> None:
        with page_layout(title="", require_auth=False):
            with ui.card().classes(
                "w-full max-w-md mx-auto p-6 border border-gray-200 shadow-sm mt-8"
            ):
                with ui.column().classes("w-full gap-1 mb-4"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("person_add", size="md").classes("text-blue-600")
                        ui.label("Create Account").classes("text-xl font-bold text-gray-900")
                    ui.label("Register a new user account for the RAG Assistant.").classes(
                        "text-xs text-gray-500"
                    )

                name_input = ui.input(
                    label="Full Name",
                    placeholder="Prof. John Doe",
                ).classes("w-full mb-2")

                email_input = ui.input(
                    label="Email Address",
                    placeholder="john@example.edu",
                ).classes("w-full mb-2")

                password_input = ui.input(
                    label="Password",
                    password=True,
                    password_toggle_button=True,
                ).classes("w-full mb-4")

                def handle_register() -> None:
                    try:
                        name = name_input.value or ""
                        email = email_input.value or ""
                        password = password_input.value or ""
                        user = api_client.register(
                            email=email.strip(),
                            password=password,
                            full_name=name.strip(),
                        )
                        ui.notify(f"Account created! Welcome, {user.full_name}!", type="positive")
                        ui.navigate.to("/dashboard")
                    except ValueError as err:
                        ui.notify(str(err), type="negative")

                with ui.column().classes("w-full gap-2"):
                    ui.button("Register", icon="person_add", on_click=handle_register).props(
                        "color=primary"
                    ).classes("w-full")

                with ui.row().classes("w-full justify-center text-xs text-gray-500 mt-4"):
                    ui.label("Already have an account?")
                    ui.link("Sign in here", "/login").classes("text-blue-600 font-semibold")
