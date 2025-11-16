#!/usr/bin/env python
"""
Launch the TarXiv dashboard web interface.

This script starts a Dash web application for exploring the TarXiv database.
Features:
- Search objects by ID
- Cone search by sky coordinates (RA/Dec)
"""

import argparse
import sys
from tarxiv.dashboard import TarxivDashboard


def main():
    parser = argparse.ArgumentParser(
        description="Launch TarXiv Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Port to run the dashboard on (default: 8050)",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to run the dashboard on (default: 127.0.0.1)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode",
    )

    parser.add_argument(
        "--reporting-mode",
        type=str,
        default=3,
        choices=[0, 1, 2, 3, 4, 5, 6, 7],
        help="Logging mode (default: 3)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("TarXiv Dashboard")
    print("=" * 60)
    print(f"Starting dashboard on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    try:
        # Initialize dashboard
        dashboard = TarxivDashboard(
            script_name="run_dashboard",
            reporting_mode=args.reporting_mode,
            debug=args.debug,
        )

        # Run server
        dashboard.run_server(port=args.port, host=args.host)

    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
        dashboard.close()
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
