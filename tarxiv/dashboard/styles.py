"""Design tokens for the dashboard.

Single source of truth for colour. ``theme_manager`` turns these into the
Mantine theme, the generated ``assets/theme.css`` custom properties and the
Plotly templates -- nothing else should hardcode a hex.
"""

PRIMARY = "#b31b1b"  # arXiv Mahogany Red

# A real 10-step brand ramp. Mantine needs ten shades to make its ``light`` /
# ``filled`` / ``outline`` variants and hover states differ; the previous
# ``[PRIMARY] * 10`` made every variant identical. Index 6 is the brand hex.
ARXIV_RED_RAMP = [
    "#fdeaea",
    "#f7cfcf",
    "#eda6a6",
    "#e37d7d",
    "#d95454",
    "#cb2a2a",
    PRIMARY,
    "#971616",
    "#7a1212",
    "#5c0d0d",
]

# Per-scheme surface/ink/accent tokens. Keys are shared between the two
# schemes so ``generate_css`` can emit both by looping.
COLORS = {
    "primary": PRIMARY,
    "light": {
        "bg": "#f7f7f8",
        "card": "#ffffff",
        "card_2": "#f2f2f4",
        "border": "rgba(18, 22, 23, 0.10)",
        "border_strong": "rgba(18, 22, 23, 0.18)",
        "ink": "#15191b",
        "ink_2": "#5a6166",
        "ink_3": "#8b9196",
        "primary_hover": "#971616",
        "primary_ink": PRIMARY,
        "primary_soft": "rgba(179, 27, 27, 0.07)",
        "primary_soft_2": "rgba(179, 27, 27, 0.14)",
        "grid": "#ececef",
        "axis": "#c9ccd0",
        "shadow": "0 1px 2px rgba(18,22,23,0.05), 0 4px 16px rgba(18,22,23,0.05)",
        "shadow_lg": "0 4px 12px rgba(18,22,23,0.08), 0 12px 40px rgba(18,22,23,0.10)",
    },
    "dark": {
        "bg": "#121617",
        "card": "#1c2224",
        "card_2": "#242c2f",
        "border": "rgba(255, 255, 255, 0.09)",
        "border_strong": "rgba(255, 255, 255, 0.16)",
        "ink": "#f2f4f5",
        "ink_2": "#a9b2b7",
        "ink_3": "#737d82",
        "primary_hover": "#cb2a2a",
        # Brand red is too dark to read as text on the dark surface; this is
        # the lighter step used wherever red carries text/icon meaning.
        "primary_ink": "#e06058",
        "primary_soft": "rgba(224, 96, 88, 0.10)",
        "primary_soft_2": "rgba(224, 96, 88, 0.18)",
        "grid": "#262e31",
        "axis": "#3d4649",
        "shadow": "0 1px 2px rgba(0,0,0,0.25), 0 4px 16px rgba(0,0,0,0.25)",
        "shadow_lg": "0 4px 12px rgba(0,0,0,0.35), 0 12px 40px rgba(0,0,0,0.40)",
    },
}

# The footer keeps its dark plate in both schemes so the partner logos hold
# contrast; exposed as a token rather than being hardcoded in ``footer_card``.
FOOTER_BG = "#1c2224"


# --------------------------------------------------------------------------
# Lightcurve series styling
#
# Both colour AND marker symbol encode the photometric BAND; the survey is
# carried by the legend group and the series label. Pairing the two channels
# is deliberate: the g/r pair sits in the 6-8 CVD separation band, which is
# only legal alongside a secondary encoding, so shape has to move with hue
# rather than being spent on the survey. Two surveys observing the same
# bandpass therefore look alike, which is the scientifically honest reading --
# they are the same measurement -- and the legend and table tell them apart.
#
# Colours were validated with the dataviz palette validator (all-pairs, i.e.
# the scatter pairlist) against both card surfaces, #ffffff and #1c2224. The
# four bands that actually co-occur in TarXiv data -- g/r from ZTF plus c/o
# from ATLAS -- pass every gate in both schemes. Beyond four series no
# ordering of eight hues can clear the all-pairs CVD floors, so the rarer
# bands below sit past that documented cap: every one is in the lightness band
# with chroma above the floor, and identity for them leans on the symbol, the
# legend label and the photometry table view (which is also the relief channel
# for amber `o` and magenta `z`, both sub-3:1 on the light surface).
# --------------------------------------------------------------------------

BAND_COLORS = {
    # band: (light, dark)
    "u": ("#4a3aa7", "#9085e9"),  # violet
    "c": ("#2a78d6", "#3987e5"),  # blue      -- validated core
    "g": ("#199e70", "#199e70"),  # green     -- validated core
    "V": ("#00663c", "#22a022"),  # deep green
    "r": ("#e34948", "#e34948"),  # red       -- validated core
    "o": ("#eda100", "#c98500"),  # amber     -- validated core
    "i": ("#952424", "#c04544"),  # deep red
    "z": ("#e87ba4", "#d55181"),  # magenta
    "w": ("#eb6834", "#d95926"),  # orange
    # Anything unrecognised folds into a neutral rather than inventing a hue.
    "Unknown": ("#8b9196", "#737d82"),
}

# Distinct shapes per band, so the green/red pair (and every other pair) stays
# separable without colour.
BAND_SYMBOLS = {
    "u": "hexagon",
    "c": "diamond",
    "g": "circle",
    "V": "star",
    "r": "square",
    "o": "triangle-up",
    "i": "pentagon",
    "z": "triangle-down",
    "w": "cross",
    "Unknown": "x",
}

# ZTF reports its red band as a capital "R"; ASAS-SN's green arrives as
# "g_ASAS-SN" from older ingests.
_BAND_ALIASES = {
    "R": "r",
    "g_asas-sn": "g",
    "g_asas_sn": "g",
    "y": "z",  # LSST y sits redward of z; share the magenta family
}


def _canonical_band(filter_name: str | None) -> str:
    """Normalise a raw filter name onto a known band key."""
    band = (filter_name or "Unknown").strip()
    if band not in BAND_COLORS:
        band = _BAND_ALIASES.get(band, _BAND_ALIASES.get(band.lower(), band))
    return band if band in BAND_COLORS else "Unknown"


def resolve_filter_style(survey: str | None, filter_name: str | None) -> dict:
    """Resolve a ``(survey, filter)`` pair to marker styling.

    Returns a dict with ``light``, ``dark`` and ``symbol`` keys. ``survey`` is
    accepted so callers can pass the full series identity (and so a future
    survey-specific override has somewhere to live), but styling is currently
    driven by the band alone -- see the note above ``BAND_COLORS``. Unknown
    bands fold to a neutral colour and the ``x`` symbol rather than generating
    new hues.
    """
    band = _canonical_band(filter_name)
    light, dark = BAND_COLORS[band]
    return {"light": light, "dark": dark, "symbol": BAND_SYMBOLS[band]}


def band_color(filter_name: str | None, scheme: str = "light") -> str:
    """Colour for a band (used by the photometry table swatches)."""
    light, dark = BAND_COLORS[_canonical_band(filter_name)]
    return dark if scheme == "dark" else light


# Categorical swatches offered when a user picks a tag colour.
TAG_SWATCHES = [
    PRIMARY,
    "#2a78d6",
    "#199e70",
    "#eda100",
    "#eb6834",
    "#4a3aa7",
    "#e87ba4",
    "#5a6166",
]


# --------------------------------------------------------------------------
# Legacy inline styles. These predate the Mantine migration; only the ones
# below are still referenced (cone result cards, the avatar in components/
# auth.py and the ORCID button in pages/user.py).
# --------------------------------------------------------------------------

CARD_STYLE = {
    "border": "1px solid var(--tarxiv-border)",
    "borderRadius": "10px",
    "padding": "16px",
    "marginBottom": "12px",
    "backgroundColor": "var(--tarxiv-card)",
    "boxShadow": "var(--tarxiv-shadow)",
}

AVATAR_STYLE = {
    "width": "32px",
    "height": "32px",
    "borderRadius": "50%",
    "objectFit": "cover",
    "border": "1px solid var(--tarxiv-border-strong)",
}

AVATAR_FALLBACK_STYLE = {
    "width": "32px",
    "height": "32px",
    "borderRadius": "50%",
    "backgroundColor": "var(--tarxiv-primary-soft-2)",
    "color": "var(--tarxiv-primary-ink)",
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "center",
    "fontWeight": "600",
    "fontSize": "14px",
}

BUTTON_STYLE = {
    "border": "none",
    "borderRadius": "8px",
    "padding": "8px 16px",
    "fontSize": "14px",
    "cursor": "pointer",
    "fontWeight": "500",
}

ORCID_BUTTON_STYLE = {
    **BUTTON_STYLE,
    "backgroundColor": "#a6ce39",  # ORCID brand green
    "color": "#102b08",
}
