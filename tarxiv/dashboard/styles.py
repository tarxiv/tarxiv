"""Styling constants for the dashboard."""

# Common styles
CARD_STYLE = {
    "border": "1px solid #ddd",
    "borderRadius": "8px",
    "padding": "20px",
    "marginBottom": "20px",
    "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
}

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
    "search_position": "#e74c3c",  # Nice bright red
    "object": "#4C84C6",  # Nice bright blue
}
