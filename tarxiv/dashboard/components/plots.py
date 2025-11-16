"""Plotting functions for the dashboard."""
from dash import dcc
import plotly.graph_objects as go
from ..styles import FILTER_COLORS


def create_lightcurve_plot(lc_data, object_id, logger=None):
    """Create a lightcurve plot from the data.

    Args:
        lc_data: List of photometry points
        object_id: Object identifier
        logger: Optional logger instance

    Returns:
        dcc.Graph or None if no valid data
    """
    if not lc_data:
        if logger:
            logger.warning({"warning": f"No lightcurve data received for object: {object_id}"})
        return None

    fig = go.Figure()
    if logger:
        logger.debug({"debug": f"Creating lightcurve plot for object: {object_id} with {len(lc_data)} points"})
        logger.debug({"debug": f"Lightcurve data sample: {lc_data[:3]}"})

    # Group data by filter/band
    filter_data = {}
    for point in lc_data:
        filter_name = point.get("filter", "Unknown")

        if filter_name not in filter_data:
            filter_data[filter_name] = {
                "mjd": [],
                "mag": [],
                "mag_err": [],
                "lim_mjd": [],
                "lim_mag": []
            }

        mjd = point.get("mjd")
        if mjd is None:
            if logger:
                logger.warning({"warning": f"Missing MJD in lightcurve point for object: {object_id}"})
            continue

        # Handle detections vs limits using detection flag
        if point.get("detection") == 1 and point.get("mag") is not None:
            filter_data[filter_name]["mjd"].append(mjd)
            filter_data[filter_name]["mag"].append(point["mag"])
            filter_data[filter_name]["mag_err"].append(point.get("mag_err", 0))
        elif point.get("detection") == 0 and point.get("limit") is not None:
            filter_data[filter_name]["lim_mjd"].append(mjd)
            filter_data[filter_name]["lim_mag"].append(point["limit"])

    # Add traces for each filter
    for filter_name, data in filter_data.items():
        color = FILTER_COLORS.get(filter_name, "gray")

        # Plot detections
        if data["mag"]:
            error_y = dict(type='data', array=data["mag_err"], visible=True) if any(data["mag_err"]) else None

            fig.add_trace(
                go.Scatter(
                    x=data["mjd"],
                    y=data["mag"],
                    mode="markers",
                    name=f"{filter_name}-band",
                    marker=dict(size=8, color=color),
                    error_y=error_y,
                    legendgroup=filter_name
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
                    marker=dict(size=8, color=color, symbol="triangle-down", opacity=0.5),
                    showlegend=False,
                    legendgroup=filter_name
                )
            )

    fig.update_layout(
        title=f"Lightcurve: {object_id}",
        xaxis_title="MJD",
        yaxis_title="Magnitude",
        yaxis=dict(autorange="reversed"),  # Magnitude scale is inverted
        hovermode="closest",
        height=500,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return dcc.Graph(figure=fig)


def create_sky_plot(results, search_ra, search_dec):
    """Create a sky position plot for cone search results.

    Args:
        results: List of objects with ra, dec, obj_name
        search_ra: Search position RA
        search_dec: Search position Dec

    Returns:
        dcc.Graph
    """
    fig = go.Figure()

    # Add search position
    fig.add_trace(
        go.Scatter(
            x=[search_ra],
            y=[search_dec],
            mode="markers",
            marker=dict(size=15, color="red", symbol="x"),
            name="Search Position",
        )
    )

    # Add found objects
    if results:
        ras = [obj["ra"] for obj in results if obj["ra"] is not None]
        decs = [obj["dec"] for obj in results if obj["dec"] is not None]
        names = [obj["obj_name"] for obj in results]

        fig.add_trace(
            go.Scatter(
                x=ras,
                y=decs,
                mode="markers",
                marker=dict(size=10, color="blue"),
                text=names,
                name="Objects",
            )
        )

    fig.update_layout(
        title="Sky Position Plot",
        xaxis_title="RA (degrees)",
        yaxis_title="Dec (degrees)",
        hovermode="closest",
        height=500,
        template="plotly_white",
    )

    return dcc.Graph(figure=fig)
