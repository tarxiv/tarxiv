"""Plotting functions for the dashboard."""

import plotly.graph_objects as go
from .theme_manager import apply_theme, get_filter_style


def empty_lightcurve_plot(
    object_id, theme_template, message="No lightcurve data available", logger=None
):
    """Build a greyed-out placeholder figure with a centred message.

    Many newer records have no lightcurve photometry to plot. Rather than
    showing a blank frame, this returns a themed figure with hidden axes, a
    translucent grey overlay and a centred annotation so the empty state is
    obvious.

    Args:
        object_id: Object identifier (used in the title)
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

    fig = go.Figure()
    fig.update_layout(
        title=f"Lightcurve: {object_id}",
        height=500,
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
                fillcolor="gray",
                opacity=0.12,
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
                font=dict(size=18, color="gray"),
            )
        ],
    )
    return apply_theme(fig, theme_template)


def create_lightcurve_plot(lc_data, object_id, theme_template, logger=None):
    """Create a lightcurve plot from the data.

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
        # color = FILTER_COLORS.get(filter_name, "gray")
        survey_label = survey_name.upper()

        # Plot detections
        if data["mag"]:
            error_y = (
                dict(type="data", array=data["mag_err"], visible=True)
                if any(data["mag_err"])
                else None
            )

            fig.add_trace(
                go.Scatter(
                    x=data["mjd"],
                    y=data["mag"],
                    mode="markers",
                    name=f"{filter_name}-band",
                    marker=dict(
                        size=8,
                        color=get_filter_style(filter_name),
                    ),
                    error_y=error_y,
                    legendgroup=survey_name,
                    legendgrouptitle_text=survey_label,
                )
            )

        # Plot limits
        if data["lim_mag"]:
            fig.add_trace(
                go.Scatter(
                    x=data["lim_mjd"],
                    y=data["lim_mag"],
                    mode="markers",
                    name=f"{filter_name}-band (limit)",
                    marker=dict(
                        size=8,
                        color=get_filter_style(filter_name),
                        symbol="triangle-down",
                        opacity=0.5,
                    ),
                    showlegend=True,
                    legendgroup=survey_name,
                    legendgrouptitle_text=survey_label,
                )
            )

    # The points existed but none were plottable (e.g. all missing mjd/mag), so
    # fall back to the same greyed-out empty state as the no-data case.
    if not fig.data:
        return empty_lightcurve_plot(object_id, theme_template, logger=logger)

    fig.update_layout(
        title=f"Lightcurve: {object_id}",
        xaxis_title="MJD",
        xaxis_tickformat=".2f",
        yaxis_title="Magnitude (mag)",
        yaxis=dict(autorange="reversed"),  # Magnitude scale is inverted
        hovermode="closest",
        height=500,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            groupclick="toggleitem",  # Allow clicking group title to toggle all items
        ),
    )

    fig = apply_theme(fig, theme_template)
    return fig
