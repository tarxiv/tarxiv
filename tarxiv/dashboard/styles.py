"""Styling constants for the dashboard."""

# Common styles
CARD_STYLE = {
    "backgroundColor": "white",
    "border": "1px solid #ddd",
    "borderRadius": "8px",
    "padding": "20px",
    "marginBottom": "20px",
    "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"
}

SECTION_STYLE = {
    "backgroundColor": "white",
    "border": "1px solid #ddd",
    "borderRadius": "8px",
    "padding": "25px",
    "marginBottom": "20px",
    "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"
}

BUTTON_STYLE = {
    "backgroundColor": "#3498db",
    "color": "white",
    "border": "none",
    "borderRadius": "4px",
    "padding": "10px 20px",
    "fontSize": "14px",
    "cursor": "pointer",
    "fontWeight": "500",
}

INPUT_STYLE = {
    "border": "1px solid #ddd",
    "borderRadius": "4px",
    "padding": "8px 12px",
    "fontSize": "14px",
}

HEADER_STYLE = {
    "textAlign": "center",
    "padding": "30px 20px",
    "backgroundColor": "#ecf0f1",
    "marginBottom": "30px"
}

CONTAINER_STYLE = {
    "maxWidth": "1200px",
    "margin": "0 auto",
    "padding": "0 20px"
}

PAGE_STYLE = {
    "backgroundColor": "#f5f6fa",
    "minHeight": "100vh",
    "fontFamily": "Arial, sans-serif"
}

# Colors
COLORS = {
    "primary": "#3498db",
    "secondary": "#2c3e50",
    "muted": "#7f8c8d",
    "success": "green",
    "warning": "orange",
    "danger": "red",
    "light": "#ecf0f1",
    "white": "white",
    "gray": "gray"
}

# Filter colors for lightcurve plots
FILTER_COLORS = {
    # ZTF filters
    "g": "green",
    "R": "red",  # ZTF uses capital R
    "i": "maroon",
    # ATLAS filters
    "c": "cyan",
    "o": "orange",
    "w": "teal",
    # ASAS-SN filters
    "V": "blue",
    "g_ASAS-SN": "green",
    # Other common filters
    "u": "violet",
    "r": "red",
    "z": "purple",
    "Unknown": "gray"
}

# Auth/navigation styling
NAVBAR_STYLE = {
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "space-between",
    "padding": "16px 24px",
    "backgroundColor": "#ffffff",
    "borderBottom": "1px solid #e5e7eb",
    "boxShadow": "0 1px 4px rgba(0,0,0,0.06)",
    "position": "sticky",
    "top": 0,
    "zIndex": 100,
}

NAV_TITLE_STYLE = {
    "display": "flex",
    "flexDirection": "column",
    "gap": "4px",
}

NAV_RIGHT_STYLE = {
    "display": "flex",
    "alignItems": "center",
    "gap": "12px",
}

USER_CHIP_STYLE = {
    "display": "flex",
    "alignItems": "center",
    "gap": "10px",
    "padding": "6px 10px",
    "border": "1px solid #e5e7eb",
    "borderRadius": "20px",
    "backgroundColor": "#f8fafc",
}

AVATAR_STYLE = {
    "width": "32px",
    "height": "32px",
    "borderRadius": "50%",
    "objectFit": "cover",
    "border": "1px solid #e5e7eb",
}

AVATAR_FALLBACK_STYLE = {
    "width": "32px",
    "height": "32px",
    "borderRadius": "50%",
    "backgroundColor": "#3498db",
    "color": "white",
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "center",
    "fontWeight": "600",
    "fontSize": "14px",
}

LOGIN_BUTTON_STYLE = {**BUTTON_STYLE, "padding": "8px 16px"}
SIGNUP_BUTTON_STYLE = {
    **BUTTON_STYLE,
    "padding": "8px 16px",
    "backgroundColor": "#1abc9c",
}
ORCID_BUTTON_STYLE = {
    **BUTTON_STYLE,
    "padding": "8px 16px",
    "backgroundColor": "#a6ce39",
    "color": "#102b08",
}
PROFILE_BUTTON_STYLE = {
    **BUTTON_STYLE,
    "padding": "6px 12px",
    "backgroundColor": "#95a5a6",
}

AUTH_MODAL_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "width": "100%",
    "height": "100%",
    "backgroundColor": "rgba(0,0,0,0.35)",
    "display": "none",
    "alignItems": "center",
    "justifyContent": "center",
    "zIndex": 200,
}

AUTH_MODAL_CONTENT_STYLE = {
    "backgroundColor": "white",
    "padding": "24px",
    "borderRadius": "12px",
    "width": "360px",
    "boxShadow": "0 8px 20px rgba(0,0,0,0.1)",
}

PROFILE_DRAWER_STYLE = {
    "position": "fixed",
    "top": 0,
    "right": "-400px",
    "width": "360px",
    "height": "100%",
    "backgroundColor": "#ffffff",
    "boxShadow": " -2px 0 12px rgba(0,0,0,0.15)",
    "padding": "24px",
    "transition": "right 0.3s ease",
    "zIndex": 150,
}

PROFILE_DRAWER_OPEN_STYLE = {**PROFILE_DRAWER_STYLE, "right": "0"}
