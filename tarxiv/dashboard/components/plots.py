"""Plotting functions for the dashboard."""

import plotly.graph_objects as go

from ..styles import COLORS, resolve_filter_style
from .theme_manager import apply_theme, scheme_from_template

# Height of the lightcurve figure, matched to the sky-view card beside it.
PLOT_HEIGHT_PX = 430


def series_label(survey_name: str | None, filter_name: str | None) -> str:
    """Legend/table label for a (survey, band) series, e.g. "ZTF g"."""
    survey = (survey_name or "Unknown").upper()
    band = filter_name or "Unknown"
    return f"{survey} {band}"


def empty_lightcurve_plot(
    object_id, theme_template, message="No lightcurve data available", logger=None
):
    """Build a greyed-out placeholder figure with a centred message.

    Many newer records have no lightcurve photometry to plot. Rather than
    showing a blank frame, this returns a themed figure with hidden axes, a
    translucent grey overlay and a centred annotation so the empty state is
    obvious.

    Args:
        object_id: Object identifier (used for logging)
        theme_template: Theme template for styling
        message: Text shown in the centre of the plot
        logger: Optional logger instance

    Returns
    -------
        go.Figure styled as an empty/greyed-out lightcurve plot
    """
    if logger:
        logger.warning({
            "warning": f"No lightcurve data to plot for object: {object_id}"
        })

    scheme = scheme_from_template(theme_template)

    fig = go.Figure()
    fig.update_layout(
        height=PLOT_HEIGHT_PX,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        shapes=[
            dict(
                type="rect",
                xref="paper",
                yref="paper",
                x0=0,
                y0=0,
                x1=1,
                y1=1,
                fillcolor=COLORS[scheme]["card_2"],
                opacity=0.6,
                line=dict(width=0),
                layer="below",
            )
        ],
        annotations=[
            dict(
                text=message,
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=15, color=COLORS[scheme]["ink_3"]),
            )
        ],
    )
    return apply_theme(fig, theme_template)


def create_lightcurve_plot(lc_data, object_id, theme_template, logger=None):
    """Create a lightcurve plot from the data.

    Colour encodes the photometric band and marker symbol encodes the survey
    (see ``styles.resolve_filter_style``), so the same bandpass observed by two
    surveys shares a colour and is told apart by shape.

    Args:
        lc_data: List of photometry points
        object_id: Object identifier
        theme_template: Theme template for styling
        logger: Optional logger instance

    Returns
    -------
        go.Figure. When there is no plottable photometry a greyed-out
        placeholder figure (with a "no data" message) is returned instead.
    """
    if not lc_data:
        return empty_lightcurve_plot(object_id, theme_template, logger=logger)

    fig = go.Figure()
    scheme = scheme_from_template(theme_template)
    surface = COLORS[scheme]["card"]

    if logger:
        logger.debug({
            "debug": f"Creating lightcurve plot for object: {object_id} with {len(lc_data)} points"
        })
        logger.debug({"debug": f"Lightcurve data sample: {lc_data[:3]}"})

    # Group data by both filter/band and survey
    grouped_data = {}
    for point in lc_data:
        filter_name = point.get("filter", "Unknown")
        survey_name = point.get("survey", "Unknown")

        # Create a unique key for filter + survey combination
        group_key = (filter_name, survey_name)

        if group_key not in grouped_data:
            grouped_data[group_key] = {
                "mjd": [],
                "mag": [],
                "mag_err": [],
                "lim_mjd": [],
                "lim_mag": [],
            }

        mjd = point.get("mjd")
        if mjd is None:
            if logger:
                logger.warning({
                    "warning": f"Missing MJD in lightcurve point for object: {object_id}"
                })
            continue

        # Handle detections vs limits using detection flag
        if point.get("detection") == 1 and point.get("mag") is not None:
            grouped_data[group_key]["mjd"].append(mjd)
            grouped_data[group_key]["mag"].append(point["mag"])
            grouped_data[group_key]["mag_err"].append(point.get("mag_err", 0))
        elif point.get("detection") == 0 and point.get("limit") is not None:
            grouped_data[group_key]["lim_mjd"].append(mjd)
            grouped_data[group_key]["lim_mag"].append(point["limit"])

    # Add traces for each filter + survey combination
    # Sort by survey name first to keep legend organized
    for (filter_name, survey_name), data in sorted(
        grouped_data.items(), key=lambda x: (x[0][1], x[0][0])
    ):
        style = resolve_filter_style(survey_name, filter_name)
        color = style[scheme]
        label = series_label(survey_name, filter_name)
        survey_label = (survey_name or "Unknown").upper()

        # Plot detections
        if data["mag"]:
            has_errors = any(data["mag_err"])
            error_y = (
                dict(
                    type="data",
                    array=data["mag_err"],
                    visible=True,
                    width=0,
                    thickness=1.2,
                    color=color,
                )
                if has_errors
                else None
            )
            if has_errors:
                hovertemplate = (
                    f"<b>{label}</b>  MJD %{{x:.2f}}<br>"
                    "%{y:.2f} ± %{customdata:.2f} mag<extra></extra>"
                )
            else:
                hovertemplate = (
                    f"<b>{label}</b>  MJD %{{x:.2f}}<br>%{{y:.2f}} mag<extra></extra>"
                )

            fig.add_trace(
                go.Scatter(
                    x=data["mjd"],
                    y=data["mag"],
                    mode="markers",
                    name=label,
                    marker=dict(
                        size=8,
                        color=color,
                        symbol=style["symbol"],
                        # Thin surface-coloured ring keeps dense epochs legible
                        line=dict(width=1, color=surface),
                    ),
                    error_y=error_y,
                    customdata=data["mag_err"],
                    hovertemplate=hovertemplate,
                    legendgroup=survey_name,
                    legendgrouptitle_text=survey_label,
                )
            )

        # Plot limits (non-detections). These share the band colour and are
        # hollow downward triangles; they stay out of the legend so it lists
        # one entry per real series.
        if data["lim_mag"]:
            fig.add_trace(
                go.Scatter(
                    x=data["lim_mjd"],
                    y=data["lim_mag"],
                    mode="markers",
                    name=f"{label} (limit)",
                    marker=dict(
                        size=9,
                        color=color,
                        symbol="triangle-down-open",
                        opacity=0.55,
                    ),
                    hovertemplate=(
                        f"<b>{label}</b> non-detection  MJD %{{x:.2f}}<br>"
                        "limit %{y:.2f} mag<extra></extra>"
                    ),
                    showlegend=False,
                    legendgroup=survey_name,
                    legendgrouptitle_text=survey_label,
                )
            )

    # The points existed but none were plottable (e.g. all missing mjd/mag), so
    # fall back to the same greyed-out empty state as the no-data case.
    if not fig.data:
        return empty_lightcurve_plot(object_id, theme_template, logger=logger)

    # Axis/legend/font/margin styling comes from the theme template; only the
    # figure-specific bits are set here. The card header carries the title.
    fig.update_layout(
        xaxis_title="MJD",
        xaxis_tickformat="d",
        yaxis_title="Apparent magnitude",
        yaxis=dict(autorange="reversed"),  # Magnitude scale is inverted
        hovermode="closest",
        height=PLOT_HEIGHT_PX,
        legend=dict(groupclick="toggleitem"),
    )

    fig = apply_theme(fig, theme_template)
    return fig
