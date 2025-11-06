from .database import TarxivDB
from .utils import TarxivModule
import dash
from dash import dcc, html, Input, Output, State, dash_table
import plotly.graph_objects as go
import json


class TarxivDashboard(TarxivModule):
    """Dashboard interface for exploring tarxiv database."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="dashboard",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        # Get couchbase connection
        self.txv_db = TarxivDB("tns", "api", script_name, reporting_mode, debug)

        # Build Dash application
        status = {"status": "setting up dash application"}
        self.logger.info(status, extra=status)
        self.app = dash.Dash(__name__, suppress_callback_exceptions=True)
        self.setup_layout()
        self.setup_callbacks()

    def setup_layout(self):
        """Set up the dashboard layout."""
        # Define common styles
        section_style = {
            "backgroundColor": "white",
            "border": "1px solid #ddd",
            "borderRadius": "8px",
            "padding": "25px",
            "marginBottom": "20px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"
        }

        button_style = {
            "backgroundColor": "#3498db",
            "color": "white",
            "border": "none",
            "borderRadius": "4px",
            "padding": "10px 20px",
            "fontSize": "14px",
            "cursor": "pointer",
            "fontWeight": "500",
        }

        input_style = {
            "border": "1px solid #ddd",
            "borderRadius": "4px",
            "padding": "8px 12px",
            "fontSize": "14px",
        }

        self.app.layout = html.Div(
            [
                # Header
                html.Div(
                    [
                        html.H1("TarXiv Database Explorer",
                                style={"marginBottom": "5px", "color": "#2c3e50"}),
                        html.P("Explore astronomical transients and their lightcurves",
                               style={"color": "#7f8c8d", "fontSize": "16px"}),
                    ],
                    style={
                        "textAlign": "center",
                        "padding": "30px 20px",
                        "backgroundColor": "#ecf0f1",
                        "marginBottom": "30px"
                    }
                ),

                # Content container
                html.Div(
                    [
                        # Search by ID section
                        html.Div(
                            [
                                html.H2("Search by Object ID",
                                        style={"marginTop": "0", "color": "#2c3e50"}),
                                html.P("Enter a TNS object name to view its metadata and lightcurve",
                                       style={"color": "#7f8c8d", "fontSize": "14px", "marginBottom": "15px"}),
                                html.Div(
                                    [
                                        dcc.Input(
                                            id="object-id-input",
                                            type="text",
                                            placeholder="Enter object ID (e.g., 2024abc)",
                                            style={**input_style, "width": "400px", "marginRight": "10px"},
                                        ),
                                        html.Button(
                                            "Search ID",
                                            id="search-id-button",
                                            n_clicks=0,
                                            style=button_style,
                                        ),
                                    ]
                                ),
                            ],
                            style=section_style,
                        ),

                        # Cone search section
                        html.Div(
                            [
                                html.H2("Cone Search by Coordinates",
                                        style={"marginTop": "0", "color": "#2c3e50"}),
                                html.P("Search for objects within a specified radius of sky coordinates",
                                       style={"color": "#7f8c8d", "fontSize": "14px", "marginBottom": "15px"}),
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Label("RA (degrees):",
                                                          style={"display": "block", "marginBottom": "5px",
                                                                "fontWeight": "500", "fontSize": "14px"}),
                                                dcc.Input(
                                                    id="ra-input",
                                                    type="number",
                                                    placeholder="0-360",
                                                    style={**input_style, "width": "150px"},
                                                ),
                                            ],
                                            style={"display": "inline-block", "marginRight": "20px"},
                                        ),
                                        html.Div(
                                            [
                                                html.Label("Dec (degrees):",
                                                          style={"display": "block", "marginBottom": "5px",
                                                                "fontWeight": "500", "fontSize": "14px"}),
                                                dcc.Input(
                                                    id="dec-input",
                                                    type="number",
                                                    placeholder="-90 to 90",
                                                    style={**input_style, "width": "150px"},
                                                ),
                                            ],
                                            style={"display": "inline-block", "marginRight": "20px"},
                                        ),
                                        html.Div(
                                            [
                                                html.Label("Radius (arcsec):",
                                                          style={"display": "block", "marginBottom": "5px",
                                                                "fontWeight": "500", "fontSize": "14px"}),
                                                dcc.Input(
                                                    id="radius-input",
                                                    type="number",
                                                    placeholder="Default: 30",
                                                    value=30,
                                                    style={**input_style, "width": "150px"},
                                                ),
                                            ],
                                            style={"display": "inline-block", "marginRight": "20px"},
                                        ),
                                        html.Div(
                                            [
                                                html.Button(
                                                    "Cone Search",
                                                    id="cone-search-button",
                                                    n_clicks=0,
                                                    style={**button_style, "marginTop": "21px"},
                                                ),
                                            ],
                                            style={"display": "inline-block", "verticalAlign": "top"},
                                        ),
                                    ]
                                ),
                            ],
                            style=section_style,
                        ),

                        # Results section
                        html.Div(
                            [
                                html.Div(id="search-status",
                                        style={"padding": "10px", "color": "#7f8c8d",
                                              "fontStyle": "italic", "fontSize": "14px"}),
                                html.Div(id="results-container"),
                            ],
                        ),
                    ],
                    style={"maxWidth": "1200px", "margin": "0 auto", "padding": "0 20px"}
                ),
            ],
            style={"backgroundColor": "#f5f6fa", "minHeight": "100vh", "fontFamily": "Arial, sans-serif"}
        )

    def setup_callbacks(self):
        """Set up the dashboard callbacks."""

        @self.app.callback(
            [Output("results-container", "children"), Output("search-status", "children")],
            [Input("search-id-button", "n_clicks"), Input("cone-search-button", "n_clicks")],
            [
                State("object-id-input", "value"),
                State("ra-input", "value"),
                State("dec-input", "value"),
                State("radius-input", "value"),
            ],
        )
        def handle_search(
            id_clicks, cone_clicks, object_id, ra, dec, radius
        ):
            """Handle search button clicks."""
            ctx = dash.callback_context

            if not ctx.triggered:
                return html.Div("Enter search criteria above."), ""

            button_id = ctx.triggered[0]["prop_id"].split(".")[0]

            try:
                # Search by ID
                if button_id == "search-id-button" and object_id:
                    status_msg = f"Searching for object: {object_id}"
                    self.logger.info({"search_type": "id", "object_id": object_id})

                    # Get metadata
                    # 'TarxivDB' expects collection names without scope prefix
                    meta = self.txv_db.get(object_id, "objects")
                    if meta is None:
                        return (
                            html.Div(
                                f"No object found with ID: {object_id}",
                                style={"color": "red"},
                            ),
                            status_msg,
                        )

                    # Display metadata
                    result = self.format_object_metadata(object_id, meta)
                    return result, status_msg

                # Cone search
                elif button_id == "cone-search-button" and ra is not None and dec is not None:
                    if radius is None:
                        radius = 30.0

                    status_msg = f"Cone search: RA={ra}, Dec={dec}, radius={radius} arcsec"
                    self.logger.info(
                        {
                            "search_type": "cone",
                            "ra": ra,
                            "dec": dec,
                            "radius": radius,
                        }
                    )

                    # Perform cone search
                    results = self.txv_db.cone_search(ra, dec, radius)

                    if not results:
                        return (
                            html.Div(
                                "No objects found in search region.",
                                style={"color": "orange"},
                            ),
                            status_msg,
                        )

                    # Display results
                    result = self.format_cone_search_results(results, ra, dec)
                    return result, status_msg

                else:
                    return html.Div("Please provide valid search criteria."), ""

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                self.logger.error({"error": error_msg})
                return html.Div(error_msg, style={"color": "red"}), "Error occurred"

    def get_lightcurve_data(self, object_id):
        """Fetch lightcurve data for an object."""
        try:
            lc_data = self.txv_db.get(object_id, "lightcurves")
            return lc_data
        except Exception as e:
            self.logger.error({"error": f"Failed to fetch lightcurve: {str(e)}"})
            return None

    def create_lightcurve_plot(self, lc_data, object_id):
        """Create a lightcurve plot from the data."""
        if not lc_data or "photometry" not in lc_data:
            return None

        fig = go.Figure()

        # Group data by filter/band
        filter_data = {}
        for point in lc_data["photometry"]:
            filter_name = point.get("filters", {}).get("name", "Unknown")

            if filter_name not in filter_data:
                filter_data[filter_name] = {
                    "mjd": [],
                    "mag": [],
                    "mag_err": [],
                    "lim_mag": []
                }

            # Handle detections vs limits
            if "magnitude" in point:
                filter_data[filter_name]["mjd"].append(point.get("jd", 0) - 2400000.5)  # Convert to MJD if needed
                filter_data[filter_name]["mag"].append(point["magnitude"])
                filter_data[filter_name]["mag_err"].append(point.get("mag_err", 0))
            elif "lim_mag" in point:
                filter_data[filter_name]["mjd"].append(point.get("jd", 0) - 2400000.5)
                filter_data[filter_name]["lim_mag"].append(point["lim_mag"])

        # Add traces for each filter
        colors = {
            "g": "green",
            "r": "red",
            "i": "orange",
            "z": "purple",
            "o": "cyan",
            "c": "blue",
            "Unknown": "gray"
        }

        for filter_name, data in filter_data.items():
            color = colors.get(filter_name, "gray")

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
                        x=[data["mjd"][i] for i, lim in enumerate(data["lim_mag"]) if lim],
                        y=[lim for lim in data["lim_mag"] if lim],
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

    def format_object_metadata(self, object_id, meta):
        """Format object metadata for display."""
        # Create a summary card
        summary_items = []

        # Extract key fields
        fields_to_display = [
            ("identifiers", "Identifiers"),
            ("ra_deg", "RA (deg)"),
            ("dec_deg", "Dec (deg)"),
            ("ra_hms", "RA (HMS)"),
            ("dec_dms", "Dec (DMS)"),
            ("object_type", "Object Type"),
            ("discovery_date", "Discovery Date"),
            ("reporting_group", "Reporting Group"),
            ("redshift", "Redshift"),
            ("host_name", "Host Name"),
        ]

        for field, label in fields_to_display:
            if field in meta and meta[field]:
                value = meta[field]
                # Format list values
                if isinstance(value, list) and len(value) > 0:
                    if isinstance(value[0], dict) and "value" in value[0]:
                        value = value[0]["value"]
                    else:
                        value = str(value[0])
                summary_items.append(html.P([html.B(f"{label}: "), str(value)]))

        # Card styling
        card_style = {
            "backgroundColor": "white",
            "border": "1px solid #ddd",
            "borderRadius": "8px",
            "padding": "20px",
            "marginBottom": "20px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"
        }

        # Fetch and plot lightcurve
        lc_data = self.get_lightcurve_data(object_id)
        lc_plot = self.create_lightcurve_plot(lc_data, object_id) if lc_data else None

        return html.Div(
            [
                # Lightcurve card
                html.Div(
                    [
                        html.H3(f"Lightcurve: {object_id}", style={"marginTop": "0"}),
                        lc_plot if lc_plot else html.P("No lightcurve data available", style={"color": "gray", "fontStyle": "italic"}),
                    ],
                    style=card_style
                ) if lc_plot or lc_data else html.Div(),

                # Metadata card
                html.Div(
                    [
                        html.H3(f"Object Metadata: {object_id}", style={"marginTop": "0"}),
                        html.Div(summary_items, style={"padding": "10px"}),
                    ],
                    style=card_style
                ),

                # Full JSON card
                html.Div(
                    [
                        html.H4("Full Metadata (JSON)", style={"marginTop": "0"}),
                        html.Pre(
                            json.dumps(meta, indent=2),
                            style={
                                "backgroundColor": "#f5f5f5",
                                "padding": "10px",
                                "maxHeight": "400px",
                                "overflow": "auto",
                                "borderRadius": "4px"
                            },
                        ),
                    ],
                    style=card_style
                ),
            ]
        )

    def format_cone_search_results(self, results, search_ra, search_dec):
        """Format cone search results for display."""
        # Card styling
        card_style = {
            "backgroundColor": "white",
            "border": "1px solid #ddd",
            "borderRadius": "8px",
            "padding": "20px",
            "marginBottom": "20px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"
        }

        # Create table data
        table_data = []
        for obj in results:
            table_data.append(
                {
                    "Object Name": obj["obj_name"],
                    "RA (deg)": f"{obj['ra']:.6f}" if obj["ra"] is not None else "N/A",
                    "Dec (deg)": f"{obj['dec']:.6f}" if obj["dec"] is not None else "N/A",
                }
            )

        # Create sky plot
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

        return html.Div(
            [
                # Summary card
                html.Div(
                    [
                        html.H3(f"Found {len(results)} object(s)", style={"marginTop": "0", "color": "#2c3e50"}),
                        html.P(f"Search coordinates: RA={search_ra:.6f}°, Dec={search_dec:.6f}°",
                               style={"color": "#7f8c8d", "fontSize": "14px"}),
                    ],
                    style=card_style
                ),

                # Sky plot card
                html.Div(
                    [
                        html.H4("Sky Position", style={"marginTop": "0"}),
                        dcc.Graph(figure=fig),
                    ],
                    style=card_style
                ),

                # Object list card
                html.Div(
                    [
                        html.H4("Object List", style={"marginTop": "0"}),
                        dash_table.DataTable(
                            data=table_data,
                            columns=[{"name": col, "id": col} for col in table_data[0].keys()]
                            if table_data
                            else [],
                            style_cell={
                                "textAlign": "left",
                                "padding": "10px",
                                "fontFamily": "Arial, sans-serif"
                            },
                            style_header={
                                "backgroundColor": "#3498db",
                                "color": "white",
                                "fontWeight": "bold",
                                "border": "1px solid #ddd"
                            },
                            style_data={
                                "border": "1px solid #ddd"
                            },
                            style_data_conditional=[
                                {
                                    "if": {"row_index": "odd"},
                                    "backgroundColor": "#f9f9f9"
                                }
                            ],
                            page_size=10,
                        ),
                    ],
                    style=card_style
                ),
            ]
        )

    def run_server(self, port=8050, host="0.0.0.0"):
        """Start the Dash server."""
        status = {"status": "starting dash server", "port": port, "host": host}
        self.logger.info(status, extra=status)
        self.app.run(debug=self.debug, host=host, port=port)

    def close(self):
        """Close database connection."""
        self.txv_db.close()
