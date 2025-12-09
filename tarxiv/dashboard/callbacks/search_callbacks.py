"""Search callbacks for the dashboard."""
from dash import html, Output, Input, State, ALL, ctx, no_update
from ..components import format_object_metadata, format_cone_search_results


def register_search_callbacks(app, txv_db, logger):
    """Register all search-related callbacks.

    Args:
        app: Dash app instance
        txv_db: TarxivDB instance
        logger: Logger instance
    """

    # Callback to handle object link clicks from cone search results
    @app.callback(
        [
            Output("object-id-input", "value", allow_duplicate=True),
            Output("search-tabs", "value", allow_duplicate=True),
            Output("search-id-button", "n_clicks", allow_duplicate=True),
        ],
        [Input({"type": "object-link", "index": ALL}, "n_clicks")],
        [State({"type": "object-id-store", "index": ALL}, "data")],
        prevent_initial_call=True
    )
    def handle_object_link_click(n_clicks_list, object_ids):
        """Handle clicks on object links in cone search results."""
        if not ctx.triggered or not any(n_clicks_list):
            return no_update, no_update, no_update

        # Find which link was clicked
        triggered_idx = ctx.triggered_id["index"] if ctx.triggered_id else None
        if triggered_idx is not None and triggered_idx < len(object_ids):
            object_id = object_ids[triggered_idx]
            # Return: populate search box, switch to ID tab, increment button clicks to trigger search
            return object_id, "id-search", 1

        return no_update, no_update, no_update

    @app.callback(
        [
            Output("results-container", "children"),
            Output("search-status", "children"),
            Output("message-banner", "children")
        ],
        [Input("search-id-button", "n_clicks"), Input("cone-search-button", "n_clicks")],
        [
            State("object-id-input", "value"),
            State("ra-input", "value"),
            State("dec-input", "value"),
            State("radius-input", "value"),
        ],
    )
    def handle_search(id_clicks, cone_clicks, object_id, ra, dec, radius):
        """Handle search button clicks."""
        if not ctx.triggered:
            return html.Div("Enter search criteria above."), "", []

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

        try:
            # Search by ID
            if button_id == "search-id-button" and object_id:
                status_msg = f"Searching for object: {object_id}"
                logger.info({"search_type": "id", "object_id": object_id})

                # Get metadata
                meta = txv_db.get(object_id, "objects")
                if meta is None:
                    error_banner = create_message_banner(
                        f"No object found with ID: {object_id}",
                        "error"
                    )
                    return html.Div(), status_msg, error_banner

                # Get lightcurve data
                lc_data = get_lightcurve_data(txv_db, object_id, logger)

                # Display metadata and lightcurve
                result = format_object_metadata(object_id, meta, lc_data, logger)
                success_banner = create_message_banner(
                    f"Successfully loaded object: {object_id}",
                    "success"
                )
                return result, status_msg, success_banner

            # Cone search
            elif button_id == "cone-search-button" and ra is not None and dec is not None:
                if radius is None:
                    radius = 30.0

                status_msg = f"Cone search: RA={ra}, Dec={dec}, radius={radius} arcsec"
                logger.info(
                    {
                        "search_type": "cone",
                        "ra": ra,
                        "dec": dec,
                        "radius": radius,
                    }
                )

                # Perform cone search
                results = txv_db.cone_search(ra, dec, radius)

                if not results:
                    warning_banner = create_message_banner(
                        "No objects found in search region.",
                        "warning"
                    )
                    return html.Div(), status_msg, warning_banner

                # Display results
                result = format_cone_search_results(results, ra, dec)
                success_banner = create_message_banner(
                    f"Found {len(results)} object(s) in search region",
                    "success"
                )
                return result, status_msg, success_banner

            else:
                warning_banner = create_message_banner(
                    "Please provide valid search criteria.",
                    "warning"
                )
                return html.Div(), "", warning_banner

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error({"error": error_msg})
            error_banner = create_message_banner(error_msg, "error")
            return html.Div(), "Error occurred", error_banner


def create_message_banner(message, message_type="info"):
    """Create a styled message banner.

    Args:
        message: Message text
        message_type: "success", "error", "warning", or "info"

    Returns
    -------
        html.Div with styled message
    """
    color_map = {
        "success": {"bg": "#d4edda", "border": "#c3e6cb", "text": "#155724"},
        "error": {"bg": "#f8d7da", "border": "#f5c6cb", "text": "#721c24"},
        "warning": {"bg": "#fff3cd", "border": "#ffeaa7", "text": "#856404"},
        "info": {"bg": "#d1ecf1", "border": "#bee5eb", "text": "#0c5460"},
    }

    colors = color_map.get(message_type, color_map["info"])

    return html.Div(
        message,
        style={
            "padding": "12px 20px",
            "marginBottom": "15px",
            "border": f"1px solid {colors['border']}",
            "borderRadius": "4px",
            "backgroundColor": colors["bg"],
            "color": colors["text"],
            "fontSize": "14px",
            "fontWeight": "500",
        }
    )


def get_lightcurve_data(txv_db, object_id, logger):
    """Fetch lightcurve data for an object.

    Args:
        txv_db: TarxivDB instance
        object_id: Object identifier
        logger: Logger instance

    Returns
    -------
        Lightcurve data or None
    """
    try:
        lc_data = txv_db.get(object_id, "lightcurves")
        logger.debug({
            "debug": f"Fetched lightcurve data for object: {object_id}: "
                     f"{len(lc_data) if lc_data else lc_data}"
        })
        return lc_data
    except Exception as e:
        logger.error({"error": f"Failed to fetch lightcurve: {str(e)}"})
        return None
