import dash_mantine_components as dmc

# switch names and descriptions constants
COOKIE_DEFAULTS = {
    "UI": {
        "label": "User Interface",
        "description": "Remember your theme and layout preferences.",
        "allowed": True,
    },
    "analytics": {
        "label": "Analytics",
        "description": "Help us improve by allowing anonymous usage data collection.",
        "allowed": True,
    },
    "remember": {
        "label": "Remember Me",
        "description": "Keep you logged in on this device.",
        "allowed": True,
    },
}


def get_cookie_popup():
    return dmc.Modal(
        title="Cookie Preferences",
        id="cookie-modal",
        opened=False,  # Managed by callback
        closeOnClickOutside=False,  # Prevents closing by clicking outside
        closeOnEscape=False,  # Prevents closing with 'Esc' key
        centered=True,  # Keeps it in the middle of the screen
        children=[
            # A series of switches for different cookie categories: UI, Analytics, Remember Me.
            # Get the switch names and descriptions from constants above.
            dmc.Stack(
                children=[
                    dmc.Switch(
                        id={"type": "permission-switch", "index": key},
                        label=value["label"],
                        description=value["description"],
                        size="md",
                        checked=value["allowed"],
                    )
                    for key, value in COOKIE_DEFAULTS.items()
                ],
                gap="md",
                mb="lg",
            ),
            # Simulate a footer with a Group
            dmc.Group(
                children=[
                    dmc.Button(
                        "Submit",
                        id="cookie-preferences-submit",
                    ),
                ],
                justify="flex-end",
            ),
        ],
    )
