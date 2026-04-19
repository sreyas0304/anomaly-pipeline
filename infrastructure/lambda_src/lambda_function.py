"""
Fleet Telemetry Anomaly Detector — Lambda Function

Triggered by Kinesis ESM from fleet-telemetry-stream.
Reads batches of truck telemetry records, applies 5 anomaly checks,
writes anomaly items to DynamoDB, and publishes CRITICAL alerts to SNS.

Environment variables (injected by Terraform):
  DYNAMODB_TABLE   - Name of the DynamoDB anomalies table
  SNS_TOPIC_ARN    - ARN of the SNS topic for CRITICAL alerts
  ENVIRONMENT      - Deployment environment tag (e.g. dev)
  ANOMALY_TTL_DAYS - Days until DynamoDB TTL expiry (e.g. 90)

TODO: Replace this file with your lambda_function.py implementation.

The handler must implement:

  def lambda_handler(event, context):
      batch_item_failures = []
      for record in event["Records"]:
          try:
              data = json.loads(base64.b64decode(record["kinesis"]["data"]))
              anomalies = detect_anomalies(data)
              for anomaly in anomalies:
                  write_to_dynamodb(anomaly)
                  if anomaly["severity"] == "CRITICAL":
                      publish_to_sns(anomaly)
          except Exception as e:
              batch_item_failures.append(
                  {"itemIdentifier": record["kinesis"]["sequenceNumber"]}
              )
      return {"batchItemFailures": batch_item_failures}

Anomaly checks (match fleet_generator.py thresholds):
  coolant_temp_c > 105.0          -> CRITICAL  (overheat)
  engine_rpm > 6500               -> CRITICAL  (high_rpm)
  active_dtc_codes non-empty      -> CRITICAL  (dtc_fault)
  fuel_level_percent < 10.0       -> WARN      (low_fuel)
  cell_signal_dbm < -95           -> CRITICAL  (signal_loss)

DynamoDB item schema:
  vin          (PK, String)
  timestamp    (SK, String)
  severity     (String) - used by GSI
  anomaly_type (String)
  value        (Number or String)
  fleet_group  (String)
  environment  (String)
  ttl          (Number) = int(time.time()) + ANOMALY_TTL_DAYS * 86400
"""

# raise NotImplementedError(
#     "Replace infrastructure/lambda_src/lambda_function.py with your implementation "
#     "before running terraform apply. See the docstring above for the full spec."
# )

"""
lambda_function.py  (DynamoDB + S3/Firehose path — no Timestream required)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fleet Telemetry — Stateless Anomaly Detector
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Trigger   : Kinesis Data Stream  →  fleet-telemetry-stream
Anomalies : DynamoDB  →  fleet_anomalies
Raw data  : Kinesis Firehose  →  S3 Parquet  (independent, Lambda ignores)
Alerts    : SNS  →  CRITICAL only

ENVIRONMENT VARIABLES:
  DYNAMODB_TABLE    fleet_anomalies
  SNS_TOPIC_ARN     arn:aws:sns:us-east-1:<ACCOUNT>:fleet-telemetry-alerts
  AWS_REGION        us-east-1
  ANOMALY_TTL_DAYS  90
"""

import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_region   = "us-east-1"
_dynamodb = boto3.resource("dynamodb", region_name=_region)
_sns      = boto3.client("sns",        region_name=_region)

DYNAMODB_TABLE   = os.environ["DYNAMODB_TABLE"]
SNS_TOPIC_ARN    = os.environ["SNS_TOPIC_ARN"]
ANOMALY_TTL_DAYS = int(os.environ.get("ANOMALY_TTL_DAYS", "90"))

WARN     = "WARN"
CRITICAL = "CRITICAL"

RPM_WARN         = 4_500
RPM_CRITICAL     = 6_500
COOLANT_WARN     = 100.0
COOLANT_CRITICAL = 105.0
FUEL_WARN        = 15.0
FUEL_CRITICAL    = 10.0
SIGNAL_WARN      = -90
SIGNAL_CRITICAL  = -95
DTC_CRITICAL_CODES = {"P0115", "P0087"}


@dataclass
class Anomaly:
    check_name : str
    severity   : str
    metric     : str
    observed   : Any
    threshold  : Any
    message    : str
    extra      : dict = field(default_factory=dict)


def _ttl_epoch(days: int) -> int:
    return int(time.time()) + (days * 86400)


# ── Checks ────────────────────────────────────────────────────────────────────

def check_engine_rpm(telemetry: dict, vin: str) -> list[Anomaly]:
    rpm = telemetry.get("engine_rpm")
    if rpm is None:
        return []
    if rpm > RPM_CRITICAL:
        return [Anomaly("engine_rpm", CRITICAL, "telemetry.engine_rpm",
                        rpm, RPM_CRITICAL,
                        f"[{vin}] Engine RPM CRITICAL: {rpm} — threshold >{RPM_CRITICAL}. Possible redline.")]
    if rpm > RPM_WARN:
        return [Anomaly("engine_rpm", WARN, "telemetry.engine_rpm",
                        rpm, RPM_WARN,
                        f"[{vin}] Engine RPM elevated: {rpm} — threshold >{RPM_WARN}.")]
    return []


def check_coolant_temp(telemetry: dict, vin: str) -> list[Anomaly]:
    temp = telemetry.get("coolant_temp_c")
    if temp is None:
        return []
    if temp > COOLANT_CRITICAL:
        return [Anomaly("coolant_temp", CRITICAL, "telemetry.coolant_temp_c",
                        temp, COOLANT_CRITICAL,
                        f"[{vin}] Coolant CRITICAL: {temp}°C — threshold >{COOLANT_CRITICAL}°C. Engine damage risk.")]
    if temp > COOLANT_WARN:
        return [Anomaly("coolant_temp", WARN, "telemetry.coolant_temp_c",
                        temp, COOLANT_WARN,
                        f"[{vin}] Coolant elevated: {temp}°C — threshold >{COOLANT_WARN}°C.")]
    return []


def check_fuel_level(telemetry: dict, vin: str) -> list[Anomaly]:
    fuel = telemetry.get("fuel_level_percent")
    if fuel is None:
        return []
    if fuel < FUEL_CRITICAL:
        return [Anomaly("fuel_level", CRITICAL, "telemetry.fuel_level_percent",
                        fuel, FUEL_CRITICAL,
                        f"[{vin}] Fuel CRITICAL: {fuel:.1f}% — threshold <{FUEL_CRITICAL}%. Immediate refuel.")]
    if fuel < FUEL_WARN:
        return [Anomaly("fuel_level", WARN, "telemetry.fuel_level_percent",
                        fuel, FUEL_WARN,
                        f"[{vin}] Fuel low: {fuel:.1f}% — threshold <{FUEL_WARN}%.")]
    return []


def check_dtc_codes(telemetry: dict, vin: str) -> list[Anomaly]:
    dtcs = telemetry.get("active_dtc_codes", [])
    if not dtcs:
        return []
    severity = CRITICAL if any(d in DTC_CRITICAL_CODES for d in dtcs) else WARN
    return [Anomaly("dtc_codes", severity, "telemetry.active_dtc_codes",
                    dtcs, "non-empty",
                    f"[{vin}] Active DTCs: {', '.join(dtcs)}.",
                    extra={"dtc_codes": dtcs})]


def check_cell_signal(gateway_meta: dict, vin: str) -> list[Anomaly]:
    dbm = gateway_meta.get("cell_signal_dbm")
    if dbm is None:
        return []
    if dbm <= SIGNAL_CRITICAL:
        return [Anomaly("cell_signal", CRITICAL, "gateway_meta.cell_signal_dbm",
                        dbm, SIGNAL_CRITICAL,
                        f"[{vin}] Cell signal CRITICAL: {dbm} dBm — dropout imminent.")]
    if dbm <= SIGNAL_WARN:
        return [Anomaly("cell_signal", WARN, "gateway_meta.cell_signal_dbm",
                        dbm, SIGNAL_WARN,
                        f"[{vin}] Cell signal degraded: {dbm} dBm.")]
    return []


def run_all_checks(record: dict) -> list[Anomaly]:
    telemetry    = record.get("telemetry",    {})
    gateway_meta = record.get("gateway_meta", {})
    vin          = record.get("vehicle",      {}).get("vin", "UNKNOWN-VIN")
    anomalies: list[Anomaly] = []
    anomalies.extend(check_engine_rpm(telemetry,     vin))
    anomalies.extend(check_coolant_temp(telemetry,   vin))
    anomalies.extend(check_fuel_level(telemetry,     vin))
    anomalies.extend(check_dtc_codes(telemetry,      vin))
    anomalies.extend(check_cell_signal(gateway_meta, vin))
    return anomalies


# ── DynamoDB writer ───────────────────────────────────────────────────────────

def write_anomalies_to_dynamodb(
    anomalies : list[Anomaly],
    record    : dict,
    event_ts  : str,
) -> None:
    """
    One DynamoDB item per anomaly.

    Sort key = timestamp#check_name ensures two checks on the same truck
    at the same second don't overwrite each other (DynamoDB PK+SK must be unique).

    TTL field causes DynamoDB to auto-delete items after ANOMALY_TTL_DAYS days.
    """
    if not anomalies:
        return

    table   = _dynamodb.Table(DYNAMODB_TABLE)
    vehicle = record.get("vehicle", {})
    vin     = vehicle.get("vin",         "UNKNOWN")
    ttl_val = _ttl_epoch(ANOMALY_TTL_DAYS)

    for anomaly in anomalies:
        sort_key     = f"{event_ts}#{anomaly.check_name}"
        observed_str = (
            json.dumps(anomaly.observed)
            if isinstance(anomaly.observed, list)
            else str(anomaly.observed)
        )

        item = {
            "vin"        : vin,
            "timestamp"  : sort_key,
            "event_ts"   : event_ts,
            "event_id"   : record.get("event_id", ""),
            "check_name" : anomaly.check_name,
            "severity"   : anomaly.severity,
            "metric"     : anomaly.metric,
            "observed"   : observed_str,
            "threshold"  : str(anomaly.threshold),
            "message"    : anomaly.message,
            "fleet_group": vehicle.get("fleet_group", "UNKNOWN"),
            "driver_id"  : vehicle.get("driver_id",   "UNKNOWN"),
            "ttl"        : ttl_val,
        }

        try:
            table.put_item(Item=item)
            logger.info("DynamoDB OK | vin=%s | check=%s | severity=%s",
                        vin, anomaly.check_name, anomaly.severity)
        except ClientError as exc:
            logger.error("DynamoDB failed | vin=%s | check=%s | %s",
                         vin, anomaly.check_name, exc)
            raise


# ── SNS publisher ─────────────────────────────────────────────────────────────

def publish_critical_to_sns(anomalies: list[Anomaly], record: dict) -> None:
    """CRITICAL only — WARN goes to DynamoDB, not SNS."""
    vehicle = record.get("vehicle", {})
    vin     = vehicle.get("vin", "UNKNOWN")

    for anomaly in anomalies:
        if anomaly.severity != CRITICAL:
            continue
        try:
            _sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"[FLEET ALERT] CRITICAL — {vin} — {anomaly.check_name}",
                Message=json.dumps({
                    "severity"   : anomaly.severity,
                    "vin"        : vin,
                    "fleet_group": vehicle.get("fleet_group"),
                    "driver_id"  : vehicle.get("driver_id"),
                    "check"      : anomaly.check_name,
                    "metric"     : anomaly.metric,
                    "observed"   : anomaly.observed,
                    "threshold"  : anomaly.threshold,
                    "message"    : anomaly.message,
                    "event_id"   : record.get("event_id"),
                    "timestamp"  : record.get("timestamp"),
                }, indent=2),
                MessageAttributes={
                    "severity":   {"DataType": "String", "StringValue": anomaly.severity},
                    "check_name": {"DataType": "String", "StringValue": anomaly.check_name},
                },
            )
            logger.info("SNS OK | vin=%s | check=%s", vin, anomaly.check_name)
        except ClientError as exc:
            logger.error("SNS failed | vin=%s | check=%s | %s",
                         vin, anomaly.check_name, exc)


# ── Handler ───────────────────────────────────────────────────────────────────

def lambda_handler(event: dict, context: object) -> dict:
    """
    Kinesis ESM entry point.

    Per record: decode → run checks → write anomalies to DynamoDB → SNS CRITICAL.
    Raw telemetry is delivered to S3 by Firehose independently — Lambda is not involved.
    Returns batchItemFailures for partial batch retry support.
    """
    kinesis_records     = event.get("Records", [])
    batch_item_failures : list[dict] = []
    total_anomalies     : int        = 0

    logger.info("Batch | count=%d", len(kinesis_records))

    for kr in kinesis_records:
        seq = kr["kinesis"]["sequenceNumber"]
        try:
            record   = json.loads(base64.b64decode(kr["kinesis"]["data"]))
            event_ts = record.get("timestamp", "")
            vin      = record.get("vehicle", {}).get("vin", "UNKNOWN")

            anomalies       = run_all_checks(record)
            total_anomalies += len(anomalies)

            if anomalies:
                logger.info("Anomalies | vin=%s | %s", vin,
                            [a.check_name for a in anomalies])
                write_anomalies_to_dynamodb(anomalies, record, event_ts)
                publish_critical_to_sns(anomalies, record)
            else:
                logger.debug("Clean | vin=%s", vin)

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Malformed | seq=%s | %s", seq, exc)
            batch_item_failures.append({"itemIdentifier": seq})
        except ClientError as exc:
            logger.error("AWS error | seq=%s | %s", seq, exc)
            batch_item_failures.append({"itemIdentifier": seq})
        except Exception as exc:
            logger.error("Unexpected | seq=%s | %s", seq, exc, exc_info=True)
            batch_item_failures.append({"itemIdentifier": seq})

    logger.info("Complete | processed=%d | anomalies=%d | failures=%d",
                len(kinesis_records), total_anomalies, len(batch_item_failures))

    return {"batchItemFailures": batch_item_failures}

