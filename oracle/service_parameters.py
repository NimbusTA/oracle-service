"""This module contains the ServiceParameters class implementation and constants."""
import json
import logging
import os
import sys
import urllib

from typing import List

from eth_account.account import Account
from eth_typing import ChecksumAddress
from substrateinterface import SubstrateInterface
from prometheus_client import start_http_server
from web3 import Web3

import log
import utils

from abi_checker import ABIChecker


DEFAULT_ERA_DELAY_TIME = '600'
DEFAULT_ERA_UPDATE_DELAY = '360'
DEFAULT_FREQUENCY_OF_REQUESTS = '180'
DEFAULT_GAS_LIMIT = '10000000'
DEFAULT_LOG_LEVEL = 'INFO'
DEFAULT_MAX_PRIORITY_FER_PER_GAS = '0'
DEFAULT_ORACLE_MASTER_CONTRACT_ABI_PATH = './assets/OracleMaster.json'
DEFAULT_TIMEOUT = '60'
DEFAULT_PROMETHEUS_METRICS_PORT = '8000'
DEFAULT_WAITING_TIME_BEFORE_SHUTDOWN = '600'

DEFAULT_SS58_FORMAT = '42'

MAX_ATTEMPTS_TO_RECONNECT = 20

logger = logging.getLogger(__name__)


class ServiceParameters:
    """This class contains the service parameters and methods to check and parse them."""
    abi: list
    account: Account
    contract_address: ChecksumAddress
    gas_limit: int
    max_priority_fee_per_gas: int

    debug_mode: bool
    era_delay_time: int
    era_duration_in_blocks: int
    era_duration_in_seconds: int
    frequency_of_requests: int
    timeout: int
    waiting_time_before_shutdown: int

    ws_urls_para: List[str]
    ws_urls_relay: List[str]

    def __init__(self):
        log_level = os.getenv('LOG_LEVEL', DEFAULT_LOG_LEVEL)
        self._check_log_level(log_level)
        log.init_log(log_level)

        logger.info("Checking configuration parameters")

        logger.info("[ENV] LOG_LEVEL: %s", log_level)

        logger.info("Checking URLs")
        logger.info("[ENV] Get 'WS_URLS_PARA'")
        self.ws_urls_para = os.getenv('WS_URLS_PARA').split(',')
        assert self.is_valid_urls(self.ws_urls_para), "Invalid urls were found in the 'WS_URLS_PARA' parameter"
        logger.info("[ENV] WS_URLS_PARA: successfully got %s urls", len(self.ws_urls_para))

        logger.info("[ENV] Get 'WS_URLS_RELAY'")
        self.ws_urls_relay = os.getenv('WS_URLS_RELAY').split(',')
        assert self.is_valid_urls(self.ws_urls_relay), "Invalid urls were found in the 'WS_URLS_RELAY' parameter"
        logger.info("[ENV] WS_URLS_RELAY: successfully got %s urls", len(self.ws_urls_relay))
        logger.info("URLs checked")

        logger.info("Checking the path to the ABI")
        oracle_master_contract_abi_path = os.getenv('ORACLE_MASTER_CONTRACT_ABI_PATH', DEFAULT_ORACLE_MASTER_CONTRACT_ABI_PATH)
        ABIChecker.check_abi_path(oracle_master_contract_abi_path)
        logger.info("The path to the ABI is checked")

        logger.info("[ENV]: Get 'DEBUG_MODE'")
        self.debug_mode = not os.getenv('DEBUG_MODE').lower() == 'false'
        logger.info("[ENV]: Get 'DEBUG_MODE': %s", self.debug_mode)

        logger.info("[ENV] 'ERA_DELAY_TIME'")
        self.era_delay_time = int(os.getenv('ERA_DELAY_TIME', DEFAULT_ERA_DELAY_TIME))
        assert self.era_delay_time >= 0, "The 'ERA_DELAY_TIME' parameter must be a non-negative integer"
        logger.info("[ENV] 'ERA_DELAY_TIME': %s", self.era_delay_time)

        logger.info("[ENV] Get 'ERA_DURATION_IN_BLOCKS'")
        era_duration_in_blocks = os.getenv('ERA_DURATION_IN_BLOCKS')
        assert era_duration_in_blocks, "The 'ERA_DURATION_IN_BLOCKS' parameter is not provided"
        self.era_duration_in_blocks = int(era_duration_in_blocks)
        assert self.era_duration_in_blocks > 0, "The 'ERA_DURATION_IN_BLOCKS' parameter must be a positive integer"
        logger.info("[ENV] Get 'ERA_DURATION_IN_BLOCKS': %s", self.era_duration_in_blocks)

        logger.info("[ENV] Get 'ERA_DURATION_IN_SECONDS'")
        era_duration_in_seconds = os.getenv('ERA_DURATION_IN_SECONDS')
        assert era_duration_in_seconds, "The 'ERA_DURATION_IN_SECONDS' parameter is not provided"
        self.era_duration_in_seconds = int(era_duration_in_seconds)
        assert self.era_duration_in_seconds > 0, "The 'ERA_DURATION_IN_SECONDS' parameter must be a positive integer"
        logger.info("[ENV] Get 'ERA_DURATION_IN_SECONDS': %s", self.era_duration_in_seconds)

        logger.info("[ENV] 'ERA_UPDATE_DELAY'")
        self.era_update_delay = int(os.getenv('ERA_UPDATE_DELAY', DEFAULT_ERA_UPDATE_DELAY))
        assert self.era_update_delay > 0, "The 'ERA_UPDATE_DELAY' parameter must be a positive integer"
        logger.info("[ENV] 'ERA_UPDATE_DELAY': %s", self.era_update_delay)

        logger.info("[ENV] 'FREQUENCY_OF_REQUESTS'")
        self.frequency_of_requests = int(os.getenv('FREQUENCY_OF_REQUESTS', DEFAULT_FREQUENCY_OF_REQUESTS))
        assert self.frequency_of_requests > 0, "The 'FREQUENCY_OF_REQUESTS' parameter must be a positive integer"
        logger.info("[ENV] 'FREQUENCY_OF_REQUESTS': %s", self.frequency_of_requests)

        logger.info("[ENV] Get 'GAS_LIMIT'")
        self.gas_limit = int(os.getenv('GAS_LIMIT', DEFAULT_GAS_LIMIT))
        assert self.gas_limit > 0, "The 'GAS_LIMIT' parameter must be a positive integer"
        logger.info("[ENV] 'GAS_LIMIT': %s", self.gas_limit)

        logger.info("[ENV] Get 'MAX_PRIORITY_FEE_PER_GAS'")
        self.max_priority_fee_per_gas = int(os.getenv('MAX_PRIORITY_FEE_PER_GAS', DEFAULT_MAX_PRIORITY_FER_PER_GAS))
        assert self.max_priority_fee_per_gas >= 0, "The 'MAX_PRIORITY_FEE_PER_GAS' parameter must be a non-negative integer"
        logger.info("[ENV] 'MAX_PRIORITY_FEE_PER_GAS': %s", self.max_priority_fee_per_gas)

        logger.info("[ENV] Get 'PROMETHEUS_METRICS_PORT'")
        prometheus_metrics_port = int(os.getenv('PROMETHEUS_METRICS_PORT', DEFAULT_PROMETHEUS_METRICS_PORT))
        assert prometheus_metrics_port > 0, "The 'PROMETHEUS_METRICS_PORT' parameter must be a non-negative integer"
        logger.info("[ENV] 'PROMETHEUS_METRICS_PORT': %s", prometheus_metrics_port)
        logger.info("Starting the Prometheus server")
        start_http_server(prometheus_metrics_port)

        logger.info("[ENV] Get 'SS58_FORMAT'")
        self.ss58_format = int(os.getenv('SS58_FORMAT', DEFAULT_SS58_FORMAT))
        logger.info("[ENV] 'SS58_FORMAT': %s", self.ss58_format)

        logger.info("[ENV] Get 'TIMEOUT'")
        self.timeout = int(os.getenv('TIMEOUT', DEFAULT_TIMEOUT))
        assert self.timeout >= 0, "The 'TIMEOUT' parameter must be a non-negative integer"
        logger.info("[ENV] 'TIMEOUT': %s", self.timeout)

        logger.info("[ENV] Get 'TYPE_REGISTRY_PRESET'")
        self.type_registry_preset = os.getenv('TYPE_REGISTRY_PRESET')
        assert self.type_registry_preset, "The 'TYPE_REGISTRY_PRESET' parameter is not provided"
        logger.info("[ENV] 'TYPE_REGISTRY_PRESET': %s", self.type_registry_preset)

        logger.info("[ENV] Get 'WAITING_TIME_BEFORE_SHUTDOWN'")
        self.waiting_time_before_shutdown = int(os.getenv(
            'WAITING_TIME_BEFORE_SHUTDOWN',
            DEFAULT_WAITING_TIME_BEFORE_SHUTDOWN,
        ))
        assert self.waiting_time_before_shutdown >= 0, \
            "The 'WAITING_TIME_BEFORE_SHUTDOWN' parameter must be a non-negative integer"
        logger.info("[ENV] 'WAITING_TIME_BEFORE_SHUTDOWN': %s", self.waiting_time_before_shutdown)

        logger.info("Creating a Web3 object")
        self.w3 = self._create_provider_forcibly(self.ws_urls_para)
        logger.info("Creating a SubstrateInterface object")
        self.substrate = self._create_interface_forcibly(self.ws_urls_relay, self.ss58_format, self.type_registry_preset)

        oracle_private_key_path = os.getenv('ORACLE_PRIVATE_KEY_PATH')
        oracle_private_key = self.get_private_key(oracle_private_key_path, os.getenv('ORACLE_PRIVATE_KEY'))
        assert oracle_private_key, "Failed to parse a private key"
        # Check a private key. Throws an exception if the length is not 32 bytes
        self.account = self.w3.eth.account.from_key(oracle_private_key)

        logger.info("Checking the contract address")
        contract_address = os.getenv('CONTRACT_ADDRESS')
        assert contract_address, "The OracleMaster address is not provided"
        self.contract_address = self.w3.toChecksumAddress(contract_address)
        self.check_contract_addresses(self.contract_address)
        logger.info("The contract address is checked")

        logger.info("Checking the ABI")
        self.abi = self.get_abi(oracle_master_contract_abi_path)
        ABIChecker.check_oracle_master_contract_abi(self.w3, self.contract_address, self.abi)
        logger.info("The ABI is checked")

        logger.info("Successfully checked configuration parameters")

    def _create_provider_forcibly(self, ws_urls: List[str]) -> Web3:
        """Force attempt to create a Web3 object."""
        for _ in range(0, MAX_ATTEMPTS_TO_RECONNECT):
            try:
                w3 = utils.create_provider(ws_urls, self.timeout)
            except utils.EXPECTED_NETWORK_EXCEPTIONS as exc:
                logger.warning("Error: %s - %s", type(exc), exc)
            else:
                return w3

        sys.exit("Failed to create a Web3 object")

    def _create_interface_forcibly(
        self, ws_urls: List[str], ss58_format: int, type_registry_preset: str) -> SubstrateInterface:
        """Force attempt to create a SubstrateInterface object."""
        for _ in range(0, MAX_ATTEMPTS_TO_RECONNECT):
            try:
                substrate = utils.create_interface(
                    urls=ws_urls,
                    ss58_format=ss58_format,
                    type_registry_preset=type_registry_preset,
                    timeout=self.timeout,
                )
            except utils.EXPECTED_NETWORK_EXCEPTIONS as exc:
                logger.warning("Error: %s - %s", type(exc), exc)
            else:
                return substrate

        sys.exit("Failed to create a SubstrateInterface object")

    def check_contract_addresses(self, *contract_addresses: str):
        """Check whether the correct contract address is provided."""
        for contract_address in contract_addresses:
            if contract_address is None:
                continue
            logger.info("Checking the address %s", contract_address)

            contract_code = self.w3.eth.get_code(Web3.toChecksumAddress(contract_address))
            if len(contract_code) < 3:
                raise ValueError(f"Incorrect contract address or the contract is not deployed: {contract_address}")

    @staticmethod
    def get_private_key(private_key_path: str, private_key: str) -> str:
        """Get a private key from a file or from an environment variable"""
        try:
            with open(private_key_path, 'r', encoding='utf-8') as file:
                pk = file.readline().strip()
                Web3().eth.account.from_key(pk)
                return pk
        except Exception as exc:
            logger.info("Failed to parse the private key from file: %s", exc)
            return private_key

    @staticmethod
    def get_abi(abi_path: str) -> list:
        """Get the ABI from file."""
        with open(abi_path, 'r', encoding='UTF-8') as file:
            return json.load(file)

    @staticmethod
    def _check_log_level(log_level: str):
        """Check the logger level based on the default list."""
        log_levels = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        if log_level not in log_levels:
            raise ValueError(f"Valid 'LOG_LEVEL_STDOUT' values: {log_levels}")

    @staticmethod
    def is_valid_urls(urls: List[str]) -> bool:
        """Check if invalid urls are in the list"""
        for url in urls:
            parsed_url = urllib.parse.urlparse(url)
            try:
                assert parsed_url.scheme in ("ws", "wss")
                assert parsed_url.params == ""
                assert parsed_url.fragment == ""
                assert parsed_url.hostname is not None
            except AssertionError:
                return False

        return True
