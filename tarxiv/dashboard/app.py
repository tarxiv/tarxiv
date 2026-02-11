"""Main dashboard application."""

import dash
from ..database import TarxivDB
from ..utils import TarxivModule
from .layouts import create_layout
from .callbacks import (
    register_style_callbacks,
    register_plotting_callbacks,
)
from .components import register_tarxiv_templates
from .components.theme_manager import generate_css


class TarxivDashboard(TarxivModule):
    """Dashboard interface for exploring tarxiv database."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="dashboard",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        # Generate CSS for themes
        status = {"status": "generating theme CSS"}
        self.logger.info(status, extra=status)
        generate_css()

        # Get couchbase connection
        self.txv_db = TarxivDB("tns", "api", script_name, reporting_mode, debug)

        # Build Dash application
        status = {"status": "setting up dash application"}
        self.logger.info(status, extra=status)
        self.app = dash.Dash(
            # __name__,
            __package__,  # Use package name enables relative imports for pages, see https://community.plotly.com/t/dash-pages-access-content-outside-pages-folder-from-inside-pages-folder/67633/5
            use_pages=True,
            # use_async=False,  # TODO: async is a thing in dash!
            suppress_callback_exceptions=True,
        )

        # Attach the class instances to the underlying Flask server.
        # This enables access to the database and logger from within Dash callbacks via current_app.config.
        self.app.server.config["TXV_DB"] = self.txv_db
        self.app.server.config["TXV_LOGGER"] = self.logger

        self.setup_layout()
        self.setup_themes()
        self.setup_callbacks()

    def setup_layout(self):
        """Set up the dashboard layout."""
        self.app.layout = create_layout()

    def setup_themes(self):
        """Set up the dashboard themes."""
        register_tarxiv_templates()

    def setup_callbacks(self):
        """Set up the dashboard callbacks."""
        register_style_callbacks(self.app, self.logger)
        register_plotting_callbacks(self.app, self.logger)

    def run_server(self, port=8050, host="0.0.0.0"):
        """Start the Dash server.

        Args:
            port: Port number
            host: Host address
        """
        status = {"status": "starting dash server", "port": port, "host": host}
        self.logger.info(status, extra=status)
        self.app.run(
            debug=self.debug, host=host, port=port, dev_tools_hot_reload=self.debug
        )

    def close(self):
        """Close database connection."""
        self.txv_db.close()
