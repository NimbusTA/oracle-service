"""This module contains the AbiChecker class, which checks ABI of different contracts."""
import logging

from os.path import exists
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.exceptions import ABIFunctionNotFound


logger = logging.getLogger(__name__)


class ABIChecker:
    """This class contains a set of methods to check ABIs of different contracts."""
    @staticmethod
    def check_abi_path(*paths: str):
        """Check paths to ABIs."""
        for path in paths:
            if not path:
                logger.warning("An empty path was found")
                continue

            logger.info("Checking the path: '%s'", path)
            if not exists(path):
                raise FileNotFoundError(f"The file with the ABI was not found: {path}")

    @staticmethod
    def check_oracle_master_contract_abi(w3: Web3, contract_addr: ChecksumAddress, abi: list):
        """Check the provided ABI of the OracleMaster contract."""
        logger.info("Checking OracleMaster ABI")
        contract = w3.eth.contract(address=contract_addr, abi=abi)
        try:
            if not hasattr(contract.functions, 'reportRelay'):
                raise ABIFunctionNotFound("The contract does not contain the 'reportRelay' function")
            contract.functions.reportRelay(0, {
                'stashAccount': '',
                'controllerAccount': '',
                'stakeStatus': 0,
                'activeBalance': 0,
                'totalBalance': 0,
                'unlocking': [],
                'claimedRewards': [],
                'stashBalance': 0,
                'slashingSpans': 0,
            }).call()

            if not hasattr(contract.functions, 'getStashAccounts'):
                raise ABIFunctionNotFound("The contract does not contain the 'getStashAccounts' function")
            contract.functions.getStashAccounts().call()
        except ValueError:
            pass
