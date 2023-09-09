"""This module contains the MetricsExporter class."""
import os

from dataclasses import dataclass
from prometheus_client import Counter, Gauge, Histogram


@dataclass
class MetricsExporter:
    """Prometheus metrics that the service exports."""
    def __init__(self, _prefix: str):
        if _prefix is None:
            _prefix = ''

        self.active_era_id = Gauge('active_era_id', "active era index", namespace=_prefix)
        self.era_update_delayed = Gauge('era_update_delayed',
                                        "1 if the era has not been updated for a long time", namespace=_prefix)
        self.is_recovery_mode_active = Gauge('is_recovery_mode_active',
                                             "1, if the recovery mode, otherwise - the default mode", namespace=_prefix)
        self.last_era_reported = Gauge('last_era_reported', "the last era that the Oracle has reported", namespace=_prefix)
        self.last_failed_era = Gauge('last_failed_era', "the last era for which sending the report ended with a revert",
                                     namespace=_prefix)
        self.oracle_balance = Gauge('oracle_balance', "the balance of the Oracle in wei", ['address'], namespace=_prefix)
        self.para_exceptions_count = Counter('para_exceptions_count', "parachain exceptions count", namespace=_prefix)
        self.previous_era_change_block_number = Gauge('previous_era_change_block_number',
                                                      "the number of the block of the previous era change", namespace=_prefix)
        self.relay_exceptions_count = Counter('relay_exceptions_count', "relay chain exceptions count", namespace=_prefix)
        self.tx_revert = Histogram('tx_revert', "reverted transactions", namespace=_prefix)
        self.tx_success = Histogram('tx_success', "successful transactions", namespace=_prefix)


prefix = os.getenv('PROMETHEUS_METRICS_PREFIX', '')
metrics_exporter = MetricsExporter(prefix)
