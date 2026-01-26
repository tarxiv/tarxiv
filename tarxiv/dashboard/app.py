"""Main dashboard application."""

import dash
from ..database import TarxivDB
from ..utils import TarxivModule
from .layouts import create_layout
from .callbacks import (
    register_search_callbacks,
    register_style_callbacks,
    register_plotting_callbacks,
)


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
        # self.app.layout = dmc.MantineProvider([create_layout()])
        self.app.layout = create_layout()

    def setup_callbacks(self):
        """Set up the dashboard callbacks."""
        register_search_callbacks(self.app, self.txv_db, self.logger)
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
