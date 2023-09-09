"""This module contains the Oracle class - the main logic of the service."""
import logging
import os
import signal
import sys
import time

from typing import Optional, Tuple

from substrateinterface import Keypair
from substrateinterface.exceptions import BlockNotFound, SubstrateRequestException
from websocket._exceptions import WebSocketConnectionClosedException

from prometheus_metrics import metrics_exporter
from report_parameters_reader import ReportParametersReader
from service_parameters import ServiceParameters
from utils import create_interface, create_provider, EXPECTED_NETWORK_EXCEPTIONS


SECOND = 1
TX_SUCCESS = 1

logger = logging.getLogger(__name__)


class Oracle:
    """This class contains methods to catch and handle active era changes."""
    era_delay_time: float
    era_delay_time_start: float
    last_era_reported: dict
    previous_active_era_id: int
    service_params: ServiceParameters
    time_of_era_immutability: float
    was_recovered: bool

    def __init__(self, service_params: ServiceParameters):
        self.service_params = service_params

        self.era_delay_time = 0
        self.era_delay_time_start = 0
        self.last_era_reported = {}
        self.previous_active_era_id = -1
        self.time_of_era_immutability = 0
        self.was_recovered = False

        logger.info("Creating an instance of the ReportParametersReader class")
        self.report_parameters_reader = ReportParametersReader(self.service_params)
        logger.info("Creating an instance of the OracleMaster contract")
        self.oracle_master_contract = self.service_params.w3.eth.contract(
            address=self.service_params.contract_address,
            abi=self.service_params.abi,
        )

    def start(self):
        """Start the service"""
        while True:
            try:
                self._restore_state()
                self._update_oracle_balance()

                possible_era_update_delay = self.service_params.era_duration_in_seconds + self.service_params.era_update_delay
                while True:
                    time_start = time.time()

                    logger.debug("Getting an active era. The previous active era id: %s", self.previous_active_era_id)
                    active_era_id, active_era_start = self._get_active_era()
                    self._assert_era_with_oracle_master(active_era_id)
                    if active_era_id > self.previous_active_era_id:
                        logger.debug("A new era has started: %s", active_era_id)
                        self.time_of_era_immutability = 0
                        time_start = time.time()
                        self._handle_era_change(active_era_id, active_era_start)
                        self.era_delay_time, self.era_delay_time_start = 0, 0
                    elif self.was_recovered:
                        logger.info("Era %s has already been processed. Waiting for the next era", active_era_id - 1)
                        self.was_recovered = False
                    logger.info("Sleep for %s seconds until the next request", self.service_params.frequency_of_requests)
                    time.sleep(self.service_params.frequency_of_requests)

                    time_end = time.time()
                    self.time_of_era_immutability += time_end - time_start
                    if self.time_of_era_immutability > possible_era_update_delay:
                        logger.warning("Era update is delayed")
                        self._shutdown_after_timeout()
            except Exception as exc:
                if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                    logger.warning("An expected exception occurred: %s - %s", type(exc), exc)
                else:
                    logger.error("An unexpected exception occurred: %s - %s", type(exc), exc)
                    if isinstance(exc, WebSocketConnectionClosedException):
                        if exc.args and exc.args[0] == 'socket is already closed.':
                            sys.exit()
                self._recover()

    def _recover(self):
        """Recover connections."""
        logger.info("Starting recovery mode")
        metrics_exporter.is_recovery_mode_active.set(True)
        self.was_recovered = True

        while True:
            try:
                logger.info("Reconnecting to the relay chain")
                self.service_params.substrate = create_interface(
                    urls=self.service_params.ws_urls_relay,
                    timeout=self.service_params.timeout,
                    substrate=self.service_params.substrate,
                )
                break
            except Exception as exc:
                if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                    logger.warning("An exception occurred: %s - %s", type(exc), exc)
                else:
                    logger.error("An exception occurred: %s - %s", type(exc), exc)

        while True:
            try:
                logger.info("Reconnecting to the parachain")
                self.service_params.w3 = create_provider(
                    timeout=self.service_params.timeout,
                    urls=self.service_params.ws_urls_para,
                    w3=self.service_params.w3,
                )
                break
            except Exception as exc:
                if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                    logger.warning("An exception occurred: %s - %s", type(exc), exc)
                else:
                    logger.error("An exception occurred: %s - %s", type(exc), exc)
        metrics_exporter.is_recovery_mode_active.set(False)
        logger.info("Recovery mode is completed")

    @metrics_exporter.para_exceptions_count.count_exceptions()
    def _assert_era_with_oracle_master(self, active_era_id: int):
        """Assert current active era with the value from the OracleMaster contract."""
        try:
            oracle_master_era_id = self.oracle_master_contract.functions.getCurrentEraId().call()
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to get the era id from the OracleMaster contract: %s", exc)
            else:
                logger.error("Failed to get the era id from the OracleMaster contract: %s", exc)
            raise exc from exc

        if active_era_id != oracle_master_era_id:
            if self.era_delay_time_start == 0:
                self.era_delay_time_start = time.time()
                return

            self.era_delay_time = time.time() - self.era_delay_time_start
            if self.service_params.era_delay_time < self.era_delay_time:
                logger.error("[OracleMaster] Era update is delayed")
                self._shutdown_after_timeout()

    def _shutdown_after_timeout(self):
        """Set the metrics that the era update is delayed and shutdown the service after timeout in N seconds"""
        metrics_exporter.era_update_delayed.set(True)
        logger.info("Sleeping for %s seconds before shutdown", self.service_params.waiting_time_before_shutdown)
        time.sleep(self.service_params.waiting_time_before_shutdown)
        os.kill(os.getpid(), signal.SIGINT)

    @metrics_exporter.relay_exceptions_count.count_exceptions()
    def _get_active_era(self, block_hash: Optional[str] = None) -> Tuple[int, int]:
        """Get an index and a timestamp of an active era."""
        try:
            if block_hash is None:
                active_era = self.service_params.substrate.query('Staking', 'ActiveEra')
            else:
                active_era = self.service_params.substrate.query('Staking', 'ActiveEra', block_hash=block_hash)
            if active_era is None or active_era.value is None:
                raise SubstrateRequestException("Staking.ActiveEra is None")
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to get the active era: %s", exc)
            else:
                logger.error("Failed to get the active era: %s", exc)
            raise exc from exc

        return active_era.value['index'], active_era.value['start']

    def _restore_state(self):
        """Restore the state when starting the service."""
        logger.info("Restoring the state for each stash")
        stash_accounts = self._get_stash_accounts()
        for stash_acc in stash_accounts:
            with metrics_exporter.para_exceptions_count.count_exceptions():
                try:
                    (era_id, is_reported) = self.oracle_master_contract.functions.isReportedLastEra(
                        self.service_params.account.address, stash_acc).call()
                except Exception as exc:
                    if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                        logger.warning("Failed to call the isReportedLastEra method from the OracleMaster contract: %s", exc)
                    else:
                        logger.error("Failed to call the isReportedLastEra method from the OracleMaster contract: %s", exc)
                    raise exc from exc
            stash = Keypair(public_key=stash_acc, ss58_format=self.service_params.ss58_format)
            self.last_era_reported[stash.public_key] = era_id if is_reported else era_id - 1
            logger.debug("Stash %s: era %s", stash.ss58_address, self.last_era_reported[stash.public_key])
        logger.info("States for each stash restored")

    def _wait_until_finalized(self, block_hash: str, block_number: int):
        """Wait until the block is finalized."""
        logger.debug("Waiting until the block %s is finalized", block_number)
        finalised_head_number = self._get_finalised_head_number()
        while finalised_head_number < block_number:
            time.sleep(SECOND)
            finalised_head_number = self._get_finalised_head_number()

        with metrics_exporter.relay_exceptions_count.count_exceptions():
            try:
                block_hash_ = self.service_params.substrate.get_block_header(block_number=block_number)['header']['hash']
            except Exception as exc:
                if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                    logger.warning("Failed to get the header of block %s: {exc}", block_number)
                else:
                    logger.error("Failed to get the header of block %s: {exc}", block_number)
                raise exc from exc
        if block_hash_ != block_hash:
            raise BlockNotFound
        logger.debug("The block is finalized: %s - %s", block_number, block_hash)

    @metrics_exporter.relay_exceptions_count.count_exceptions()
    def _get_finalised_head_number(self) -> Optional[int]:
        """Get the number of the finalised head."""
        try:
            finalised_head = self.service_params.substrate.get_chain_finalised_head()
            finalised_head_number = self.service_params.substrate.get_block_header(finalised_head)['header']['number']
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.error("Failed to get the finalised head: %s", exc)
            else:
                logger.error("Failed to get the finalised head: %s", exc)
            raise exc from exc

        return finalised_head_number

    def _handle_era_change(self, active_era_id: int, era_start_timestamp: int):
        """Read staking parameters for each stash account separately from the block where
        the era is changed, generate the transaction body, sign and send to the OracleMaster in the parachain.
        """
        logger.info("Active era index: %s, start timestamp: %s", active_era_id, era_start_timestamp)
        metrics_exporter.active_era_id.set(active_era_id)

        stash_accounts = self._get_stash_accounts()
        if not stash_accounts:
            logger.info("No stash accounts found: waiting for the next era")
            self.previous_active_era_id = active_era_id
            return

        block_hash, block_number = self._find_last_block(active_era_id)
        self._wait_until_finalized(block_hash, block_number)
        metrics_exporter.previous_era_change_block_number.set(block_number)

        for stash_acc in stash_accounts:
            stash = Keypair(public_key=stash_acc, ss58_format=self.service_params.ss58_format)
            if self.last_era_reported.get(stash.public_key, 0) >= active_era_id - 1:
                logger.info("The report has already been sent for the stash %s", stash.ss58_address)
                continue
            staking_parameters = self.report_parameters_reader.get_stash_staking_parameters(stash, block_hash)
            logger.info("The parameters are read. Preparing the transaction body. Stash: %s; Era: %s; Staking_parameters: %s",
                        stash.ss58_address, active_era_id - 1, staking_parameters)
            tx = self._create_tx(active_era_id - 1, staking_parameters)
            if not self.service_params.debug_mode:
                self._sign_and_send_to_para(tx, stash, active_era_id - 1)
            else:
                logger.info("Skipping sending the transaction for the stash %s: running in debug mode", stash.ss58_address)
            self._update_oracle_balance()
            self.last_era_reported[stash.public_key] = active_era_id - 1

        logger.info("Waiting for the next era")
        metrics_exporter.last_era_reported.set(active_era_id - 1)
        self.previous_active_era_id = active_era_id

    @metrics_exporter.para_exceptions_count.count_exceptions()
    def _get_stash_accounts(self) -> tuple:
        """Get stash accounts from the OracleMaster contract."""
        try:
            stash_accounts = self.oracle_master_contract.functions.getStashAccounts().call()
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to get stash accounts from the OracleMaster contract: %s", exc)
            else:
                logger.error("Failed to get stash accounts from the OracleMaster contract: %s", exc)
            raise exc from exc

        return stash_accounts

    @metrics_exporter.para_exceptions_count.count_exceptions()
    def _update_oracle_balance(self):
        """Update the balance of the oracle and expose it to Prometheus."""
        try:
            balance = self.service_params.w3.eth.get_balance(self.service_params.account.address)
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to get the balance of the oracle: %s", exc)
            else:
                logger.error("Failed to get the balance of the oracle: %s", exc)
            raise exc from exc
        metrics_exporter.oracle_balance.labels(self.service_params.account.address).set(balance)

    @metrics_exporter.relay_exceptions_count.count_exceptions()
    def _get_block_hash(self, block_number: int) -> str:
        """Get the hash of the block by its number.

        Throws the BlockNotFound error if any exception occurs.
        """
        try:
            block_hash = self.service_params.substrate.get_block_hash(block_number)
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.error("Can't find the required block: %s", exc)
            else:
                logger.error("Can't find the required block: %s", exc)
            raise BlockNotFound from exc

        return block_hash

    def _find_last_block(self, era_id: int) -> Tuple[str, int]:
        """Find the last block of the previous era."""
        current_block_number = self._get_finalised_head_number()

        start = 0
        block_hash, block_number = None, None
        if current_block_number - self.service_params.era_duration_in_blocks > 0:
            start = current_block_number - self.service_params.era_duration_in_blocks
        end = current_block_number

        while start <= end:
            mid = (start + end) // 2
            block_hash = self._get_block_hash(mid)
            era_id_specified, _ = self._get_active_era(block_hash)
            if era_id_specified < era_id:
                start = mid + 1
            else:
                end = mid - 1
            if era_id_specified == era_id:
                block_number = mid - 1
                block_hash = self._get_block_hash(block_number)
            else:
                block_number = mid
        logger.info("Block hash: %s. Block number: %s", block_hash, block_number)

        return block_hash, block_number

    @metrics_exporter.para_exceptions_count.count_exceptions()
    def _create_tx(self, era_id: int, staking_parameters: dict) -> dict:
        """Create a transaction body."""
        try:
            nonce = self.service_params.w3.eth.get_transaction_count(self.service_params.account.address)
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to get the transaction count: %s", exc)
            else:
                logger.error("Failed to get the transaction count: %s", exc)
            raise exc from exc

        try:
            tx = self.oracle_master_contract.functions.reportRelay(era_id, staking_parameters).buildTransaction({
                'from': self.service_params.account.address,
                'gas': self.service_params.gas_limit,
                'maxPriorityFeePerGas': self.service_params.max_priority_fee_per_gas,
                'nonce': nonce,
            })
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to build the transaction: %s", exc)
            else:
                logger.error("Failed to build the transaction: %s", exc)
            raise exc from exc

        return tx

    @metrics_exporter.para_exceptions_count.count_exceptions()
    def _sign_and_send_to_para(self, tx: dict, stash: Keypair, era_id: int) -> bool:
        """Sign a transaction and send it to the OracleMaster in the parachain."""
        try:
            self.service_params.w3.eth.call(dict((k, v) for k, v in tx.items() if v))
            del tx['from']
        except ValueError as exc:
            msg = exc.args[0]["message"] if isinstance(exc.args[0], dict) else str(exc)
            logger.warning("The report for '%s' era %s will probably fail with %s", stash.ss58_address, era_id, msg)
            metrics_exporter.last_failed_era.set(era_id)
            metrics_exporter.tx_revert.observe(1)
            return False

        tx_signed = self.service_params.w3.eth.account.sign_transaction(tx, self.service_params.account.privateKey)
        logger.info("Sending a transaction for the stash %s", stash.ss58_address)
        tx_hash = self.service_params.w3.eth.send_raw_transaction(tx_signed.rawTransaction)
        logger.info("Transaction hash: %s", tx_hash.hex())
        tx_receipt = self.service_params.w3.eth.wait_for_transaction_receipt(tx_hash)
        logger.debug("Transaction receipt: %s", tx_receipt)

        if tx_receipt.status == TX_SUCCESS:
            logger.info("The report for the stash '%s' era %s was sent successfully", stash.ss58_address, era_id)
            metrics_exporter.tx_success.observe(int(True))
            return True

        logger.warning("[era %s] The transaction status for the stash '%s': reverted", era_id, stash.ss58_address)
        metrics_exporter.last_failed_era.set(era_id)
        metrics_exporter.tx_revert.observe(int(True))
        return False
