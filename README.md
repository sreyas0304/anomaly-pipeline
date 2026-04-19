# Fleet Anomaly Pipeline

A standalone fleet telemetry system that simulates 25 trucks across 10 US regions, streams live telemetry to AWS Kinesis, and will eventually detect anomalies via a serverless processing pipeline.

## Overview

A Python simulator generates per-second telemetry for a 25-truck fleet, each truck assigned to one of 10 regional corridors (I-5, I-10, I-90, etc.) and optionally injected with one of 7 anomaly profiles. Payloads are batched and pushed to an AWS Kinesis Data Stream. The downstream pipeline (in progress) will archive records to S3, run anomaly detection, and alert on DTC codes.

---

## Repository Structure

```
anomaly-pipeline/
├── tools/
│   └── fleet_generator.py        # 25-truck telemetry simulator
├── src/
│   ├── rules_engine/
│   │   └── app.py                # Anomaly detection engine (in progress)
│   └── timeout_watcher/
│       └── app.py                # Vehicle timeout monitor (in progress)
├── tests/
│   └── test_anomaly_rules.py     # Unit tests (in progress)
├── infrastructure/
│   ├── environments/
│   │   └── dev/
│   │       ├── main.tf           # Root module — wires kinesis + iam modules
│   │       ├── variables.tf
│   │       ├── outputs.tf
│   │       ├── backend.tf        # S3 + DynamoDB remote state
│   │       └── config.tfvars     # Dev variable values
│   └── modules/
│       ├── kinesis/              # aws_kinesis_stream resource
│       └── iam/                  # IAM user, access key, inline policy
├── .github/
│   └── workflows/
│       └── terraform-dev.yml     # CI: plan on PR, apply on push to develop
├── requirements.txt
└── CLAUDE.md                     # Project context and session history
```

---

## Fleet Simulator

**File:** `tools/fleet_generator.py`

Simulates 25 trucks pushing telemetry every second for 1000 iterations.

### Fleet Composition

| Region | Trucks | Cities |
|---|---|---|
| West-Coast | 3 | Oakland, Los Angeles, Sacramento |
| Pacific-Northwest | 2 | Seattle, Portland |
| Southwest | 3 | Phoenix, Las Vegas, Albuquerque |
| Mountain | 3 | Denver, Salt Lake City, Boise |
| Midwest | 3 | Chicago, Minneapolis, Cleveland |
| Great-Plains | 2 | Kansas City, Omaha |
| South-Central | 3 | Houston, Dallas, Oklahoma City |
| Southeast | 3 | Atlanta, Miami, Charlotte |
| Mid-Atlantic | 2 | Philadelphia, Washington DC |
| Northeast | 1 | New York |

### Anomaly Profiles

| Profile | Count | Behavior |
|---|---|---|
| healthy | 10 (40%) | Normal drift only |
| reckless | 4 (16%) | Random hard braking, RPM spikes |
| blowout | 3 (12%) | Steady tire pressure degradation |
| overheat | 3 (12%) | Rising coolant temp, triggers DTC P0115 |
| timeout | 2 (8%) | Random vehicle stops (1% chance/iter) |
| fuel_drain | 2 (8%) | Accelerated fuel consumption, triggers DTC P0087 |
| signal_loss | 1 (4%) | GPS blackout every 50 iterations for 5 iterations |

### Telemetry Payload

Each record includes:

```json
{
  "event_id": "uuid",
  "timestamp": "2026-04-08T12:00:00Z",
  "gateway_meta": {
    "imei": "...",
    "cell_signal_dbm": -75,
    "firmware_version": "v4.2.1"
  },
  "vehicle": {
    "vin": "WC1TRUCK0000000001",
    "driver_id": "EMP-1001",
    "fleet_group": "West-Coast",
    "ignition_status": "ON",
    "odometer_miles": 123456.7
  },
  "telemetry": {
    "gps": { "lat": 37.3688, "lon": -122.0363, "heading_degrees": 270, "satellites_locked": 9 },
    "speed_mph": 62.4,
    "engine_rpm": 1872,
    "throttle_position_percent": 73.4,
    "brake_pedal_status": 0,
    "coolant_temp_c": 88.2,
    "fuel_level_percent": 74.5,
    "tire_pressures_psi": { "steer_left": 105.1, "steer_right": 104.9, ... },
    "active_dtc_codes": []
  }
}
```

---

## Infrastructure

Provisioned with Terraform, managed via CI on the `develop` branch.

### AWS Resources (Dev)

| Resource | Value |
|---|---|
| Kinesis Data Stream | `fleet-telemetry-stream` |
| Stream mode | PROVISIONED — 1 shard |
| Retention | 24 hours |
| Region | us-east-1 |
| IAM producer user | `fleet-telemetry-producer` |
| Producer permissions | `kinesis:PutRecord`, `PutRecords`, `DescribeStream`, `DescribeStreamSummary` |

### Remote State

| Resource | Value |
|---|---|
| S3 bucket | `fleet-telemetry-tfstate` |
| DynamoDB lock table | `fleet-telemetry-tf-lock` |
| State key | `fleet-telemetry/terraform.tfstate` |
| Region | us-east-1 |

> The S3 bucket and DynamoDB table are pre-existing and not managed by Terraform.

### Terraform Modules

- **`modules/kinesis/`** — `aws_kinesis_stream` only
- **`modules/iam/`** — `aws_iam_user`, `aws_iam_access_key`, `aws_iam_user_policy` (least-privilege inline policy)

All resources are tagged: `Project=fleet-telemetry`, `Environment=dev`, `ManagedBy=terraform`.

---

## CI/CD

**Workflow:** `.github/workflows/terraform-dev.yml`
**Branch:** `develop` only
**Paths:** `infrastructure/**`

| Event | Action |
|---|---|
| Pull request to `develop` | `terraform plan` — result posted as PR comment |
| Push to `develop` | `terraform apply -auto-approve` |

### Required GitHub Secrets

| Secret | Purpose |
|---|---|
| `TF_AWS_ACCESS_KEY_ID` | CI IAM user access key |
| `TF_AWS_SECRET_ACCESS_KEY` | CI IAM user secret key |

### CI IAM User Permissions

```
kinesis:*             on stream ARN
iam:CreateUser, DeleteUser, GetUser, CreateAccessKey, DeleteAccessKey,
    PutUserPolicy, DeleteUserPolicy, GetUserPolicy
s3:GetObject, PutObject, ListBucket  on tfstate bucket
dynamodb:GetItem, PutItem, DeleteItem  on lock table
```

---

## Running Locally

### Prerequisites

```bash
pip install -r requirements.txt
```

### Configure AWS credentials (producer user)

```bash
export AWS_ACCESS_KEY_ID=<producer access key>
export AWS_SECRET_ACCESS_KEY=<producer secret key>
export AWS_DEFAULT_REGION=us-east-1
```

Retrieve credentials from Terraform output:
```bash
cd infrastructure/environments/dev
terraform output -raw producer_access_key_id
terraform output -raw producer_secret_access_key
```

### Run the simulator

```bash
python tools/fleet_generator.py
```

If AWS credentials are not configured, the simulator falls back to console-only output (no Kinesis writes).

### Verify data reaching the stream

```bash
aws kinesis describe-stream-summary \
  --stream-name fleet-telemetry-stream \
  --region us-east-1
```

---

## Roadmap

| Component | Status |
|---|---|
| Kinesis Data Stream | Done |
| IAM producer user + least-privilege policy | Done |
| Terraform remote state (S3 + DynamoDB) | Done |
| CI/CD — plan on PR, apply on push | Done |
| Fleet simulator (25 trucks, 7 anomaly profiles) | Done |
| Kinesis Firehose → S3 (raw record archiving) | Planned |
| AWS Glue crawler + Athena (ad-hoc SQL) | Planned |
| DynamoDB live truck state table (keyed on VIN) | Planned |
| Lambda anomaly consumer + SNS alerting | Planned |
| Staging environment | Planned |
