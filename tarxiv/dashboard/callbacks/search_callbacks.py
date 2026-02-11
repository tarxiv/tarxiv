"""Search callbacks for the dashboard."""

from dash import html, Output, Input, State, ALL, ctx, no_update
import dash_mantine_components as dmc
from ..schemas import (
    MetadataResponseModel,
    LightcurveResponseModel,
    ConeSearchResponseModel,
)
from ..components import (
    format_object_metadata,
    format_cone_search_results,
)
import requests
from pydantic import ValidationError


def register_search_callbacks(app, txv_db, logger):
    """Register all search-related callbacks.

    Args:
        app: Dash app instance
        txv_db: TarxivDB instance
        logger: Logger instance
    """

    # # Callback to handle object link clicks from cone search results
    # @app.callback(
    #     [
    #         Output("object-id-input", "value", allow_duplicate=True),
    #         Output("search-tabs", "value", allow_duplicate=True),
    #         Output("search-id-button", "n_clicks", allow_duplicate=True),
    #     ],
    #     [Input({"type": "object-link", "index": ALL}, "n_clicks")],
    #     [State({"type": "object-id-store", "index": ALL}, "data")],
    #     prevent_initial_call=True,
    # )
    # def handle_object_link_click(n_clicks_list, object_ids):
    #     """Handle clicks on object links in cone search results."""
    #     if not ctx.triggered or not any(n_clicks_list):
    #         return no_update, no_update, no_update

    #     # Find which link was clicked
    #     triggered_idx = ctx.triggered_id["index"] if ctx.triggered_id else None
    #     if triggered_idx is not None and triggered_idx < len(object_ids):
    #         object_id = object_ids[triggered_idx]
    #         # Return: populate search box, switch to ID tab, increment button clicks to trigger search
    #         return object_id, "id-search", 1

    #     return no_update, no_update, no_update

    @app.callback(
        [
            Output("results-container", "children", allow_duplicate=True),
            Output("search-status", "children", allow_duplicate=True),
            Output("message-banner", "children", allow_duplicate=True),
            Output("lightcurve-store", "data"),
        ],
        [Input("search-id-button", "n_clicks")],
        [State("object-id-input", "value")],
        prevent_initial_call=True,
    )
    def handle_id_search(n_clicks, object_id):
        """Handle search by ID button clicks."""
        if not n_clicks:
            return no_update, no_update, no_update, no_update

        try:
            if not object_id:
                warning_banner = create_message_banner(
                    "Please provide an object ID.", "warning"
                )
                logger.warning({"warning": "No object ID provided for search."})
                return no_update, "", warning_banner, no_update

            status_msg = f"Searching for object: {object_id}"
            logger.info({"search_type": "id", "object_id": object_id})

            response_meta = requests.post(
                url=f"http://tarxiv-api:9001/get_object_meta/{object_id}",  # TODO: Fix URL
                timeout=10,
                headers={
                    "accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": "TOKEN",
                },
            )
            meta = None
            logger.info(
                {"info": f"Metadata response status: {response_meta.status_code}"}
            )
            # logger.info({"info": f"Metadata response text: {response_meta.text}"})
            if response_meta.status_code == 200:
                try:
                    data = MetadataResponseModel.model_validate_json(response_meta.text)
                    # meta = MetadataResponseModel.model_validate(response_meta.json())
                except ValidationError as e:
                    logger.error(
                        {
                            "error": f"Failed to parse metadata for object {object_id}: {str(e)}"
                        }
                    )
                    error_banner = create_message_banner(
                        f"Failed to parse metadata for object: {object_id}", "error"
                    )
                    return no_update, "", error_banner, no_update
            else:
                logger.error(
                    {
                        "error": f"Metadata request failed for object {object_id}: "
                        f"Status {response_meta.status_code}"
                    }
                )
                error_banner = create_message_banner(
                    f"Metadata request failed for object: {object_id}", "error"
                )
                return no_update, "", error_banner, no_update

            meta = data.model_dump()
            # Get metadata
            # meta = txv_db.get(object_id, "objects")
            if meta is None:
                error_banner = create_message_banner(
                    f"No object found with ID: {object_id}", "error"
                )
                logger.warning({"warning": f"Object ID not found: {object_id}"})
                return no_update, status_msg, error_banner, no_update

            # Get lightcurve data
            lc_data = get_lightcurve_data(txv_db, object_id, logger)

            # Display metadata
            result = format_object_metadata(object_id, meta, logger)
            success_banner = create_message_banner(
                f"Successfully loaded object: {object_id}", "success"
            )
            logger.info({"info": f"Object {object_id} loaded successfully."})

            store_data = {"data": lc_data, "id": object_id}

            return result, status_msg, success_banner, store_data

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error({"error": error_msg})
            error_banner = create_message_banner(error_msg, "error")
            return html.Div(), "Error occurred", error_banner, no_update

    @app.callback(
        [
            Output("results-container", "children", allow_duplicate=True),
            Output("search-status", "children", allow_duplicate=True),
            Output("message-banner", "children", allow_duplicate=True),
            Output("cone-search-store", "data"),
        ],
        [Input("cone-search-button", "n_clicks")],
        [
            State("ra-input", "value"),
            State("dec-input", "value"),
            State("radius-input", "value"),
        ],
        prevent_initial_call=True,
    )
    def handle_cone_search(n_clicks, ra, dec, radius):
        """Handle cone search button clicks."""
        if not n_clicks:
            return no_update, no_update, no_update, no_update

        try:
            if ra is None or dec is None:
                warning_banner = create_message_banner(
                    "Please provide valid RA and Dec coordinates.", "warning"
                )
                return html.Div(), "", warning_banner, no_update

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
            results = get_cone_search_results(txv_db, ra, dec, radius, logger)

            # Display results
            result = format_cone_search_results(results, ra, dec)
            success_banner = create_message_banner(
                f"Found {len(results)} object(s) in search region", "success"
            )
            logger.info({"info": f"Cone search found {len(results)} objects."})

            store_data = {"results": results, "ra": ra, "dec": dec}

            return result, status_msg, success_banner, store_data

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error({"error": error_msg})
            error_banner = create_message_banner(error_msg, "error")
            return html.Div(), "Error occurred", error_banner, no_update


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

    return dmc.Alert(
        # message,
        title=message.capitalize(),
        style={
            "padding": "12px 20px",
            "marginBottom": "15px",
            "border": f"1px solid {colors['border']}",
            "borderRadius": "4px",
            "backgroundColor": colors["bg"],
            "color": colors["text"],
            "fontSize": "14px",
            "fontWeight": "500",
        },
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
        # lc_data = txv_db.get(object_id, "lightcurves")
        response_lc = requests.post(
            url=f"http://tarxiv-api:9001/get_object_lc/{object_id}",  # TODO: Fix URL
            timeout=10,
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": "TOKEN",
            },
        )
        # response_lc.text will contain a list of LightcurveResponseSingle
        data = None
        logger.info({"info": f"Lightcurve response status: {response_lc.status_code}"})
        if response_lc.status_code == 200:
            try:
                data = LightcurveResponseModel.validate_json(response_lc.text)

                logger.info(
                    {
                        "success": f"Parsed lightcurve for object {object_id}: {len(data)} points"
                    }
                )

            except ValidationError as e:
                logger.error(
                    {
                        "error": f"Failed to parse lightcurve for object {object_id}: {str(e)}"
                    }
                )
                return None
        else:
            logger.error(
                {
                    "error": f"Lightcurve request failed for object {object_id}: "
                    f"Status {response_lc.status_code}"
                }
            )
            return None

        return LightcurveResponseModel.dump_python(data)
    except Exception as e:
        logger.error({"error": f"Failed to fetch lightcurve: {str(e)}"})
        return None


# def parse_response(type: BaseModel, response: requests.Response, logger) -> BaseModel | None:
#     """Parse a response into a Pydantic model.

#     Args:
#         type: Pydantic model class
#         response: HTTP response
#         logger: Logger instance

#     Returns
#     -------
#         Parsed model instance or None
#     """
#     try:
#         if response.status_code == 200:
#             try:
#                 data = type.model_validate_json(response.text)
#                 return data
#             except ValidationError as e:
#                 logger.error(
#                     {
#                         "error": f"Failed to parse response: {str(e)}"
#                     }
#                 )
#                 return None
#         else:
#             logger.error(
#                 {
#                     "error": f"Request failed: Status {response.status_code}"
#                 }
#             )
#             return None
#     except Exception as e:
#         logger.error({"error": f"Failed to parse response: {str(e)}"})
#         return None


def get_cone_search_results(txv_db, ra, dec, radius, logger) -> list:
    """Perform a cone search.

    Args:
        txv_db: TarxivDB instance
        ra: Right Ascension
        dec: Declination
        radius: Search radius in arcseconds
        logger: Logger instance

    Returns
    -------
        List of search results
    """
    try:
        # results = txv_db.cone_search(ra, dec, radius)
        response_cone = requests.post(
            url="http://tarxiv-api:9001/cone_search",
            timeout=10,
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": "TOKEN",
            },
            json={"ra": ra, "dec": dec, "radius": radius},
        )

        results = []
        logger.info(
            {"info": f"Cone search response status: {response_cone.status_code}"}
        )

        if response_cone.status_code == 200:
            try:
                data = ConeSearchResponseModel.validate_json(response_cone.text)
                results = ConeSearchResponseModel.dump_python(data)

                logger.debug(
                    {
                        "debug": f"Cone search results for RA={ra}, Dec={dec}, "
                        f"radius={radius} arcsec: {len(results)} objects found"
                    }
                )
            except ValidationError as e:
                logger.error(
                    {"error": f"Failed to parse cone search results: {str(e)}"}
                )
        else:
            logger.error(
                {
                    "error": f"Cone search request failed: Status {response_cone.status_code}"
                }
            )

        return results
    except Exception as e:
        logger.error({"error": f"Cone search failed: {str(e)}"})
        return []
