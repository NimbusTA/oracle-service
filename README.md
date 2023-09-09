# nimbus-oracle
The oracle service for the Nimbus protocol.


## How it works
* Upon the start daemon determines the reportable era and retrieves the list of stash accounts to report for.
* If no stash accounts are found, the service waits for the beginning of the next era. Otherwise, daemon starts collecting staking parameters for each stash account separately, signs and sends transactions to the OracleMaster contract.
* After a report has been sent for all stash accounts, it moves on to waiting for the next era.


## Requirements
* Python 3.9


## Setup
```shell
pip install -r requirements.txt
```


## Run
The service receives its configuration parameters from environment variables. Export required parameters from the list below and start the service:
```shell
bash run.sh
```

To stop the service, send a SIGINT or SIGTERM signal to the process.


## List of functions from the OracleMaster that are used by the service
* `getCurrentEraId`
* `isReportedLastEra`
* `getStashAccounts`
* `reportRelay`


## Configuration options
#### Required
* `CONTRACT_ADDRESS` - The OracleMaster contract address. Example: `0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84`.
* `ERA_DURATION_IN_BLOCKS` - The duration of era in blocks.
* `ERA_DURATION_IN_SECONDS` - The duration of era in seconds. It is required for setting the SIGALRM timer.
* `ORACLE_PRIVATE_KEY_PATH` - The path to the oracle private key file. **Required if the `ORACLE_PRIVATE_KEY` parameter is not specified**.
* `ORACLE_PRIVATE_KEY` - The oracle private key, 0x prefixed. It is used if there is no file with the key. **Required if the `ORACLE_PRIVATE_KEY_PATH` is not specified**.
* `TYPE_REGISTRY_PRESET` - The type registry preset for the relay chain.
* `WS_URLS_PARA` - WS URLs of the parachain nodes. **Must be comma-separated**, example: `ws://localhost:10059/,ws://localhost:10055/`.
* `WS_URLS_RELAY` - WS URLs of the relay chain nodes. **Must be comma-separated**, example: `ws://localhost:9959/,ws://localhost:9957/`.

#### Optional
* `DEBUG_MODE` - If the value is `true` (case insensitive), the service doesn't send transactions but simply prepares reports.
* `ERA_DELAY_TIME` - The maximum delay in seconds for which an era can be updated comparing to the OracleMaster before the service stops working. The default value is `600`.
* `ERA_UPDATE_DELAY` - The maximum delay in seconds for which an era can be updated before the service stops working. The default value is `360`.
* `FREQUENCY_OF_REQUESTS` - The frequency of sending requests to receive the active era in seconds. The default value is `180`.
* `GAS_LIMIT` - The predefined gas limit for a composed transaction. The default value is `10000000`.
* `LOG_LEVEL` - The logging level of the logging module: `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. The default level is `INFO`.
* `MAX_PRIORITY_FEE_PER_GAS` - The [maxPriorityFeePerGas](https://ethereum.org/en/developers/docs/gas/#priority-fee) transaction parameter. The default value is `0`.
* `ORACLE_MASTER_CONTRACT_ABI_PATH` - The path to the OracleMaster ABI file. The default value is `./assets/OracleMaster.json`.
* `PROMETHEUS_METRICS_PORT` - The port of the Prometheus HTTP server. The default value is `8000`.
* `PROMETHEUS_METRICS_PREFIX` - The prefix for Prometheus metrics. The default value is ``.
* `SS58_FORMAT` - The ss58 format for the relay chain. The default value is `42`.
* `TIMEOUT` - The time in seconds before trying to connect to any node if the first attempt is not successful. The default value is `60`.
* `WAITING_TIME_BEFORE_SHUTDOWN` - Waiting time in seconds before shutting the service down. The default value is `600`.


## Prometheus metrics

The Prometheus exporter provides the following metrics.

| name                                                                    | description                                                              | frequency                                                   |
|-------------------------------------------------------------------------|--------------------------------------------------------------------------|-------------------------------------------------------------|
| **active_era_id**                                      <br> *Gauge*     | The index of the active era                                              | Every relay chain block                                     |
| **era_update_delayed**                                 <br> *Gauge*     | 1 if the era has not been updated for a long time                        | Every relay chain block                                     |
| **is_recovery_mode_active**                            <br> *Gauge*     | Is the service in recovery mode: 1, if yes, otherwise - the default mode | Starting and ending of recovery mode                        |
| **last_era_reported**                                  <br> *Gauge*     | The last era that the Oracle has reported                                | After completing a sending of reports for an era            |
| **last_failed_era**                                    <br> *Gauge*     | the last era for which sending the report ended with a revert            | During sending a report for an era                          |
| **oracle_balance**                                     <br> *Gauge*     | The balance of the Oracle in wei                                         | Every change of era                                         |
| **para_exceptions_count**                              <br> *Counter*   | The counter of exceptions in the parachain                               | Every exception in the parachain                            |
| **previous_era_change_block_number**                   <br> *Gauge*     | the number of the block of the previous era change                       | Every change of era, if at least one stash account is found |
| **relay_exceptions_count**                             <br> *Counter*   | The counter of exceptions in the relay chain                             | Every exception in the relay chain                          |
| **tx_revert**                                          <br> *Histogram* | The number of failed transactions                                        | Every reverted transaction                                  |
| **tx_success**                                         <br> *Histogram* | The number of successful transactions                                    | Every successful transaction                                |

