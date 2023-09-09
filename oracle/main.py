#!/usr/bin/env python3
"""This module is an entrypoint which creates required instances and starts the service."""
import logging
import signal
import sys

from service_parameters import ServiceParameters
from oracle import Oracle


logger = logging.getLogger(__name__)


def main():
    """Create instances and start the service"""
    signal.signal(signal.SIGTERM, stop_signal_handler)
    signal.signal(signal.SIGINT, stop_signal_handler)

    try:
        service_params = ServiceParameters()
        oracle = Oracle(service_params=service_params)
    except Exception as exc:
        sys.exit(f"An exception occurred: {type(exc)} - {exc}")

    oracle.start()


def stop_signal_handler(sig: int = None, frame=None):
    """Handle the signal and terminate the process"""
    sys.exit(f"Receiving a signal: {sig}")


if __name__ == '__main__':
    main()
