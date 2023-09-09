"""This module contains the ReportParametersReader class."""
import logging

from dataclasses import dataclass
from typing import Union
from substrateinterface import Keypair
from substrateinterface.exceptions import SubstrateRequestException

from prometheus_metrics import metrics_exporter
from service_parameters import ServiceParameters
from utils import EXPECTED_NETWORK_EXCEPTIONS


logger = logging.getLogger(__name__)

IDLE = 0
NOMINATOR = 1
VALIDATOR = 2


@dataclass
class ReportParametersReader:
    """This class contains a set of methods for reading data for the Oracle report."""
    service_params: ServiceParameters

    def get_stash_staking_parameters(self, stash: Keypair, block_hash: str) -> dict:
        """Get staking parameters for the specific stash from the specific block or from the chain head."""
        logger.info("Reading staking parameters for the stash '%s'", stash.ss58_address)

        stash_free_balance = self._get_stash_free_balance(stash, block_hash)
        stake_status = self._get_stake_status(stash, block_hash)
        staking_ledger_result = self._get_ledger_data(block_hash, stash)

        if staking_ledger_result is None:
            return {
                'stashAccount': stash.public_key,
                'controllerAccount': stash.public_key,
                'stakeStatus': 3,  # means that the stake status is None
                'activeBalance': 0,
                'totalBalance': 0,
                'unlocking': [],
                'claimedRewards': [],
                'stashBalance': stash_free_balance,
                'slashingSpans': 0,
            }

        controller = staking_ledger_result['controller']

        return {
            'stashAccount': stash.public_key,
            'controllerAccount': controller.public_key,
            'stakeStatus': stake_status,
            'activeBalance': staking_ledger_result['active'],
            'totalBalance': staking_ledger_result['total'],
            'unlocking': [{'balance': elem['value'], 'era': elem['era']} for elem in staking_ledger_result['unlocking']],
            'claimedRewards': [],  # put aside until storage proof has been implemented
            # ^^^^^^^^^^^^^^^^^^^ staking_ledger_result['claimedRewards']
            'stashBalance': stash_free_balance,
            'slashingSpans': staking_ledger_result['slashingSpans_number'],
        }

    @metrics_exporter.relay_exceptions_count.count_exceptions()
    def _get_ledger_data(self, block_hash: str, stash: Keypair) -> Union[dict, None]:
        """Get data of the ledger."""
        try:
            controller = self.service_params.substrate.query(
                module='Staking',
                storage_function='Bonded',
                params=[stash.ss58_address],
                block_hash=block_hash,
            )
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to get the controller of the stash '%s': %s", stash.ss58_address, exc)
            else:
                logger.error("Failed to get the controller of the stash '%s': %s", stash.ss58_address, exc)
            raise exc from exc
        if controller is None or controller.value is None:
            return None
        controller = Keypair(ss58_address=controller.value)

        try:
            ledger = self.service_params.substrate.query(
                module='Staking',
                storage_function='Ledger',
                params=[controller.ss58_address],
                block_hash=block_hash,
            )
            if ledger is None or ledger.value is None:
                raise SubstrateRequestException("Staking.Ledger is None")
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to get the ledger '%s': %s", controller.ss58_address, exc)
            else:
                logger.error("Failed to get the ledger '%s': %s", controller.ss58_address, exc)
            raise exc from exc

        result = {'controller': controller, 'stash': stash}
        result.update(ledger.value)

        try:
            slashing_spans = self.service_params.substrate.query(
                module='Staking',
                storage_function='SlashingSpans',
                params=[controller.ss58_address],
                block_hash=block_hash,
            )
            result['slashingSpans_number'] = 0 if slashing_spans.value is None else len(slashing_spans.value['prior'])
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to get the slashing spans of the ledger '%s': %s", controller.ss58_address, exc)
            else:
                logger.error("Failed to get the slashing spans of the ledger '%s': %s", controller.ss58_address, exc)
            raise exc from exc

        return result

    @metrics_exporter.relay_exceptions_count.count_exceptions()
    def _get_stash_free_balance(self, stash: Keypair, block_hash: str) -> int:
        """Get stash accounts free balances."""
        try:
            account_info = self.service_params.substrate.query(
                module='System',
                storage_function='Account',
                params=[stash.ss58_address],
                block_hash=block_hash,
            )
            if account_info is None or account_info.value is None:
                raise SubstrateRequestException("System.Account is None")
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to get the account '%s' info: %s", stash.ss58_address, exc)
            else:
                logger.error("Failed to get the account '%s' info: %s", stash.ss58_address, exc)
            raise exc from exc

        return account_info.value['data']['free']

    @metrics_exporter.relay_exceptions_count.count_exceptions()
    def _get_stake_status(self, stash: Keypair, block_hash: str) -> int:
        """Get a status of the stash account."""
        try:
            staking_nominators = self.service_params.substrate.query_map('Staking', 'Nominators', block_hash=block_hash)
            if staking_nominators is None:
                raise SubstrateRequestException("Staking.Nominators is None")
        except Exception as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to get nominators: %s", exc)
            else:
                logger.error("Failed to get nominators: %s", exc)
            raise exc from exc
        nominators = set(nominator.value for nominator, _ in staking_nominators)
        if stash.ss58_address in nominators:
            return NOMINATOR

        try:
            staking_validators = self.service_params.substrate.query('Session', 'Validators', block_hash=block_hash)
            if staking_validators is None or staking_validators.value is None:
                raise SubstrateRequestException("Session.Validators is None")
        except EXPECTED_NETWORK_EXCEPTIONS as exc:
            if type(exc) in EXPECTED_NETWORK_EXCEPTIONS:
                logger.warning("Failed to get validators: %s", exc)
            else:
                logger.error("Failed to get validators: %s", exc)
            raise exc from exc
        validators = set(validator for validator in staking_validators.value)
        if stash.ss58_address in validators:
            return VALIDATOR

        return IDLE
