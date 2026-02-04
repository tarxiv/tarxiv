"""Styling constants for the dashboard."""

# Common styles
CARD_STYLE = {
    "border": "1px solid #ddd",
    "borderRadius": "8px",
    "padding": "20px",
    "marginBottom": "20px",
    "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
}

SECTION_STYLE = {
    "border": "1px solid #ddd",
    "borderRadius": "8px",
    "padding": "25px",
    "marginBottom": "20px",
    "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
}

BUTTON_STYLE = {
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
    "marginBottom": "30px",
}

CONTAINER_STYLE = {
    "margin": "0 auto",
    "padding": "10px",
}

PAGE_STYLE = {
    "minHeight": "100vh",
    "fontFamily": "Arial, sans-serif",
    "backgroundColor": "var(--mantine-color-bg)",
}

# Colors
# COLORS = {
#     "primary": "#3498db",
#     "secondary": "#2c3e50",
#     "muted": "#7f8c8d",
#     "success": "green",
#     "warning": "orange",
#     "danger": "red",
#     "light": "#ecf0f1",
#     "white": "white",
#     "gray": "gray",
# }
COLORS = {
    "primary": "#b31b1b",  # Mahogany Red
    "bg_light": "#fefefe",  # White
    "bg_dark": "#121617",  # Onyx
    "surface_light": "#ebebf1",  # Ghost White
    "surface_dark": "#212729",  # Jet Black
    # "card_light": "#FDF6F6",  # Snow Pink
    # "card_light": "#FEFAFA",  # Off White
    "card_light": "#FDF4F4",  # Soft Pink
    "card_dark": "#212729",  # Jet Black
    "vlight_gray": "#F5F5F8",  # Very Light Gray
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
    "Unknown": "gray",
}
