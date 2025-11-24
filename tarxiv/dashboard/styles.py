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
