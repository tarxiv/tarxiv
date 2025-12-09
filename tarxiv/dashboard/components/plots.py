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

    Returns
    -------
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
                "lim_mag": []
            }

        mjd = point.get("mjd")
        if mjd is None:
            if logger:
                logger.warning({"warning": f"Missing MJD in lightcurve point for object: {object_id}"})
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
    for (filter_name, survey_name), data in sorted(grouped_data.items(), key=lambda x: (x[0][1], x[0][0])):
        color = FILTER_COLORS.get(filter_name, "gray")
        survey_label = survey_name.upper()

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
                    legendgroup=survey_name,
                    legendgrouptitle_text=survey_label
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
                    showlegend=True,
                    legendgroup=survey_name,
                    legendgrouptitle_text=survey_label
                )
            )

    fig.update_layout(
        title=f"Lightcurve: {object_id}",
        xaxis_title="MJD",
        yaxis_title="Magnitude (mag)",
        yaxis=dict(autorange="reversed"),  # Magnitude scale is inverted
        hovermode="closest",
        height=500,
        template="plotly_white",
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            groupclick="toggleitem"  # Allow clicking group title to toggle all items
        )
    )

    return dcc.Graph(figure=fig)


def create_sky_plot(results, search_ra, search_dec):
    """Create a sky position plot for cone search results with spherical projection.

    Args:
        results: List of objects with ra, dec, obj_name
        search_ra: Search position RA (degrees, 0-360)
        search_dec: Search position Dec (degrees, -90 to 90)

    Returns
    -------
        dcc.Graph
    """
    # Convert RA from [0, 360] to [-180, 180] for proper spherical projection
    # This centers RA=0 at the middle of the map
    def convert_ra(ra):
        """Convert RA to longitude format for plotting."""
        if ra is None:
            return None
        # Shift RA so it's centered properly: 0-360 -> -180 to 180
        lon = ra if ra <= 180 else ra - 360
        return lon

    search_lon = convert_ra(search_ra)

    fig = go.Figure()

    # Add found objects first (so search position appears on top)
    if results:
        lons = [convert_ra(obj["ra"]) for obj in results if obj["ra"] is not None]
        lats = [obj["dec"] for obj in results if obj["dec"] is not None]
        names = [obj["obj_name"] for obj in results]

        fig.add_trace(
            go.Scattergeo(
                lon=lons,
                lat=lats,
                mode="markers",
                marker=dict(size=8, color="blue", line=dict(width=0.5, color='white')),
                text=names,
                hovertemplate="<b>%{text}</b><br>RA: %{lon:.4f}°<br>Dec: %{lat:.4f}°<extra></extra>",
                name="Objects",
            )
        )

    # Add search position on top
    fig.add_trace(
        go.Scattergeo(
            lon=[search_lon],
            lat=[search_dec],
            mode="markers",
            marker=dict(size=15, color="red", symbol="x", line=dict(width=2, color='darkred')),
            hovertemplate="<b>Search Position</b><br>RA: %{lon:.4f}°<br>Dec: %{lat:.4f}°<extra></extra>",
            name="Search Position",
        )
    )

    # Use Aitoff projection (common in astronomy) centered on the search position
    fig.update_geos(
        projection_type="aitoff",
        showcountries=False,
        showcoastlines=False,
        showland=False,
        showocean=False,
        showlakes=False,
        showrivers=False,
        bgcolor="rgba(240, 240, 255, 0.3)",
        projection_rotation=dict(
            lon=search_lon if search_lon is not None else 0,
            lat=search_dec if search_dec is not None else 0,
            roll=0
        ),
        lataxis=dict(
            showgrid=True,
            gridcolor="lightgray",
            gridwidth=0.5,
        ),
        lonaxis=dict(
            showgrid=True,
            gridcolor="lightgray",
            gridwidth=0.5,
        ),
    )

    fig.update_layout(
        title=dict(
            text=f"Sky Map (RA: {search_ra:.4f}°, Dec: {search_dec:.4f}°)",
            x=0.5,
            xanchor="center"
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="center",
            x=0.5
        ),
        height=600,
        margin=dict(l=0, r=0, t=50, b=0),
    )

    return dcc.Graph(figure=fig)
