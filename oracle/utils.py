"""This module contains a set of methods of creating Substrate interfaces and web3 providers and some constants."""
import asyncio
import logging
import time

from socket import gaierror
from typing import List, Optional
from websocket._exceptions import WebSocketAddressException, WebSocketConnectionClosedException

from substrateinterface import SubstrateInterface
from substrateinterface.exceptions import BlockNotFound, SubstrateRequestException
from web3 import Web3
from web3.exceptions import BadFunctionCallOutput, TimeExhausted, ValidationError
from websockets.exceptions import ConnectionClosedError, InvalidMessage, InvalidStatusCode


logger = logging.getLogger(__name__)


EXPECTED_NETWORK_EXCEPTIONS = (
    asyncio.TimeoutError,
    BadFunctionCallOutput,
    BlockNotFound,
    BrokenPipeError,
    ConnectionClosedError,
    ConnectionRefusedError,
    ConnectionResetError,
    gaierror,
    InvalidMessage,
    InvalidStatusCode,
    SubstrateRequestException,
    TimeExhausted,
    TimeoutError,
    ValidationError,
    WebSocketAddressException,
    WebSocketConnectionClosedException,
)


def create_provider(urls: List[str], timeout: int = 60, w3: Web3 = None) -> Web3:
    """Create the web3 websocket provider with one of the nodes given in the list."""
    while True:
        for url in urls:
            try:
                if w3 is None or not w3.isConnected():
                    provider = Web3.WebsocketProvider(url)
                    w3 = Web3(provider)
                else:
                    logger.info("[web3py] Not recreating a provider: the connection is already established to %s", url)
                if not w3.isConnected():
                    raise ConnectionRefusedError
            except RuntimeError:
                w3 = None
            except Exception as exc:
                logger.warning("[web3py] Failed to connect to the node: %s - %s", type(exc), exc)
            else:
                logger.info("[web3py] Successfully connected to %s", url)
                return w3
        logger.error("[web3py] Failed to connect to any node")
        logger.info("Timeout: %s seconds", timeout)
        time.sleep(timeout)


def create_interface(
    urls: List[str],
    ss58_format: Optional[int] = None,
    type_registry_preset: Optional[str] = None,
    timeout: int = 60,
    substrate: SubstrateInterface = None,
) -> SubstrateInterface:
    """Create the Substrate interface with one of the nodes given in the list., if there is no an undesirable one."""
    while True:
        for url in urls:
            try:
                if substrate:
                    substrate.websocket.shutdown()
                    substrate.websocket.connect(url)
                else:
                    substrate = SubstrateInterface(url, ss58_format=ss58_format, type_registry_preset=type_registry_preset)
                    substrate.update_type_registry_presets()
            except Exception as exc:
                logger.warning("[substrateinterface] Failed to connect to %s: %s", url, exc)
                if isinstance(exc.args[0], str) and exc.args[0].find("Unsupported type registry preset") != -1:
                    raise ValueError(exc.args[0]) from exc
            else:
                logger.info("[substrateinterface] The connection was made at the address: %s", url)
                return substrate
        logger.error("[substrateinterface] Failed to connect to any node")
        logger.info("Timeout: %s seconds", timeout)
        time.sleep(timeout)
