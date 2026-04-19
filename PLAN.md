# Fleet Telemetry — Session 2 Infrastructure Plan

## Context

Session 1 provisioned `fleet-telemetry-stream` (Kinesis) and `fleet-telemetry-producer` (IAM user)
via Terraform with CI wired to the develop branch.

Session 2 completes the end-to-end pipeline: S3 data lake, Kinesis Firehose (raw archiving),
Glue (schema crawling + Athena), DynamoDB (anomaly persistence), SNS (alerting), Lambda
(anomaly detector), and a Grafana read-only IAM user.

**Planning decisions:**
- `fleet-telemetry-stream` and `fleet-telemetry-producer` are kept unchanged (no rename).
  Only NEW Session 2 resources use the `dev-` prefix.
- `infrastructure/lambda_src/lambda_function.py` placeholder exists — **replace before apply**.
- SNS alert email: `srsawant.iu@gmail.com`
- S3 bucket: `dev-fleet-telemetry-lake-<YOUR_ACCOUNT_ID>` — set `account_id` in config.tfvars.
- `default_tags` added to the AWS provider (new modules need no inline tag blocks).
- `archive` provider added for the lambda zip data source.

---

## Status: IMPLEMENTED ✓ (not yet applied)

All Terraform files have been written. **Three items are blocking `terraform apply`:**

| # | Blocking Item | Status |
|---|---|---|
| 1 | Implement `infrastructure/lambda_src/lambda_function.py` | **TODO** |
| 2 | Set `account_id` in `infrastructure/environments/dev/config.tfvars` | **TODO** |
| 3 | Add Session 2 CI IAM permissions to the CI IAM user | **TODO** |

---

## New Files Created (Session 2)

### New Terraform Modules

| Module | Path | Key Resources |
|---|---|---|
| s3_datalake | `infrastructure/modules/s3_datalake/` | S3 bucket, public access block, AES256 SSE, lifecycle (IA@30d → Glacier@90d → expire@365d) |
| sns | `infrastructure/modules/sns/` | SNS topic + email subscription |
| dynamodb | `infrastructure/modules/dynamodb/` | Table (VIN+timestamp key), severity GSI, TTL on `ttl` attribute |
| firehose | `infrastructure/modules/firehose/` | Firehose delivery stream + IAM role (dynamic partition by fleet_group, GZIP, 64MB/60s buffer) |
| glue | `infrastructure/modules/glue/` | Glue DB + JSON classifier ($[*]) + hourly crawler + IAM role |
| lambda_detector | `infrastructure/modules/lambda_detector/` | Lambda (python3.12, 256MB, 60s timeout) + Kinesis ESM (batch 250, window 10s) + CW log group (30d) + IAM role |
| grafana_user | `infrastructure/modules/grafana_user/` | IAM user + access key + read-only Athena/Glue/S3 policy |

### Lambda Source

`infrastructure/lambda_src/lambda_function.py` — **placeholder, must be replaced**

Required implementation:
```python
def lambda_handler(event, context):
    # 1. Decode Kinesis base64 records → JSON
    # 2. Run 5 anomaly checks per record:
    #      coolant_temp_c > 105.0       → CRITICAL, overheat
    #      engine_rpm > 6500            → CRITICAL, high_rpm
    #      active_dtc_codes non-empty   → CRITICAL, dtc_fault
    #      fuel_level_percent < 10.0    → WARN,     low_fuel
    #      cell_signal_dbm < -95        → CRITICAL, signal_loss
    # 3. Write anomalies to DynamoDB (vin, timestamp, severity, anomaly_type, value, fleet_group, ttl)
    # 4. Publish CRITICAL anomalies to SNS
    # 5. Return {"batchItemFailures": [...]} for partial batch error handling
```

Env vars: `DYNAMODB_TABLE`, `SNS_TOPIC_ARN`, `ENVIRONMENT`, `ANOMALY_TTL_DAYS`

---

## Modified Files (Session 2)

| File | Change |
|---|---|
| `infrastructure/environments/dev/main.tf` | Added archive provider, default_tags, locals, 7 new module calls |
| `infrastructure/environments/dev/variables.tf` | Added `alert_email`, `account_id` variables |
| `infrastructure/environments/dev/outputs.tf` | Added 6 new outputs (S3, DynamoDB, SNS, Grafana keys) |
| `infrastructure/environments/dev/config.tfvars` | Added `alert_email`, `account_id = "<YOUR_ACCOUNT_ID>"` |
| `.gitignore` | Added `*.zip` |

## Unchanged Files

- `infrastructure/environments/dev/backend.tf`
- `infrastructure/modules/kinesis/*`
- `infrastructure/modules/iam/*`
- `tools/fleet_generator.py`
- `.github/workflows/terraform-dev.yml`

---

## Complete AWS Resource Names

| Resource | AWS Name |
|---|---|
| Kinesis stream | `fleet-telemetry-stream` (existing, Session 1) |
| IAM producer user | `fleet-telemetry-producer` (existing, Session 1) |
| S3 data lake | `dev-fleet-telemetry-lake-<ACCOUNT_ID>` |
| SNS topic | `dev-fleet-telemetry-alerts` |
| DynamoDB table | `dev-fleet-anomalies` |
| Firehose stream | `dev-fleet-telemetry-raw-delivery` |
| Glue database | `dev_fleet_telemetry_db` |
| Glue classifier | `dev-fleet-telemetry-json-classifier` |
| Glue crawler | `dev-fleet-telemetry-crawler` |
| Lambda function | `dev-fleet-telemetry-detector` |
| Lambda IAM role | `dev-fleet-telemetry-lambda-role` |
| Firehose IAM role | `dev-fleet-telemetry-firehose-role` |
| Glue IAM role | `dev-fleet-telemetry-glue-role` |
| Grafana IAM user | `dev-fleet-telemetry-grafana` |
| CloudWatch log group | `/aws/lambda/dev-fleet-telemetry-detector` |

---

## CI IAM User — Additional Permissions Required (Session 2)

Add a second inline policy `ci-session2` to the CI IAM user **before pushing to develop**.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3DataLake",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket", "s3:DeleteBucket", "s3:GetBucketLocation",
        "s3:GetBucketVersioning", "s3:PutBucketPublicAccessBlock",
        "s3:GetBucketPublicAccessBlock", "s3:PutEncryptionConfiguration",
        "s3:GetEncryptionConfiguration", "s3:PutLifecycleConfiguration",
        "s3:GetLifecycleConfiguration", "s3:ListBucket",
        "s3:PutObject", "s3:GetObject", "s3:DeleteObject",
        "s3:GetBucketAcl", "s3:GetBucketCORS", "s3:GetBucketWebsite",
        "s3:GetBucketLogging", "s3:GetBucketRequestPayment",
        "s3:GetBucketTagging", "s3:PutBucketTagging",
        "s3:GetAccelerateConfiguration", "s3:GetBucketObjectLockConfiguration",
        "s3:GetReplicationConfiguration", "s3:ListBucketMultipartUploads"
      ],
      "Resource": [
        "arn:aws:s3:::dev-fleet-telemetry-lake-*",
        "arn:aws:s3:::dev-fleet-telemetry-lake-*/*"
      ]
    },
    {
      "Sid": "SNS",
      "Effect": "Allow",
      "Action": [
        "sns:CreateTopic", "sns:DeleteTopic", "sns:GetTopicAttributes",
        "sns:SetTopicAttributes", "sns:Subscribe", "sns:Unsubscribe",
        "sns:ListSubscriptionsByTopic", "sns:TagResource", "sns:UntagResource",
        "sns:ListTagsForResource"
      ],
      "Resource": "arn:aws:sns:us-east-1:*:dev-fleet-telemetry-alerts"
    },
    {
      "Sid": "DynamoDB",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable", "dynamodb:DeleteTable", "dynamodb:DescribeTable",
        "dynamodb:UpdateTable", "dynamodb:TagResource", "dynamodb:UntagResource",
        "dynamodb:ListTagsOfResource", "dynamodb:DescribeTimeToLive",
        "dynamodb:UpdateTimeToLive", "dynamodb:DescribeContinuousBackups",
        "dynamodb:UpdateContinuousBackups"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:*:table/dev-fleet-anomalies"
    },
    {
      "Sid": "Firehose",
      "Effect": "Allow",
      "Action": [
        "firehose:CreateDeliveryStream", "firehose:DeleteDeliveryStream",
        "firehose:DescribeDeliveryStream", "firehose:UpdateDestination",
        "firehose:TagDeliveryStream", "firehose:UntagDeliveryStream",
        "firehose:ListTagsForDeliveryStream"
      ],
      "Resource": "arn:aws:firehose:us-east-1:*:deliverystream/dev-fleet-telemetry-raw-delivery"
    },
    {
      "Sid": "Glue",
      "Effect": "Allow",
      "Action": [
        "glue:CreateDatabase", "glue:DeleteDatabase", "glue:GetDatabase",
        "glue:UpdateDatabase", "glue:CreateCrawler", "glue:DeleteCrawler",
        "glue:GetCrawler", "glue:UpdateCrawler", "glue:StartCrawler",
        "glue:StopCrawler", "glue:CreateClassifier", "glue:DeleteClassifier",
        "glue:GetClassifier", "glue:UpdateClassifier",
        "glue:TagResource", "glue:UntagResource", "glue:GetTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "Lambda",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction", "lambda:DeleteFunction",
        "lambda:UpdateFunctionCode", "lambda:UpdateFunctionConfiguration",
        "lambda:GetFunction", "lambda:GetFunctionConfiguration",
        "lambda:AddPermission", "lambda:RemovePermission",
        "lambda:CreateEventSourceMapping", "lambda:DeleteEventSourceMapping",
        "lambda:GetEventSourceMapping", "lambda:UpdateEventSourceMapping",
        "lambda:TagResource", "lambda:UntagResource", "lambda:ListTags"
      ],
      "Resource": [
        "arn:aws:lambda:us-east-1:*:function:dev-fleet-telemetry-detector",
        "arn:aws:lambda:us-east-1:*:event-source-mapping:*"
      ]
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup", "logs:DeleteLogGroup",
        "logs:PutRetentionPolicy", "logs:DeleteRetentionPolicy",
        "logs:DescribeLogGroups", "logs:ListTagsLogGroup",
        "logs:TagLogGroup", "logs:UntagLogGroup",
        "logs:ListTagsForResource", "logs:TagResource", "logs:UntagResource"
      ],
      "Resource": "arn:aws:logs:us-east-1:*:log-group:/aws/lambda/dev-fleet-telemetry-detector:*"
    },
    {
      "Sid": "IAMRolesAndUsers",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole", "iam:DeleteRole", "iam:GetRole",
        "iam:AttachRolePolicy", "iam:DetachRolePolicy",
        "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:GetRolePolicy",
        "iam:PassRole", "iam:TagRole", "iam:UntagRole",
        "iam:ListRolePolicies", "iam:ListAttachedRolePolicies",
        "iam:CreateUser", "iam:DeleteUser", "iam:GetUser",
        "iam:CreateAccessKey", "iam:DeleteAccessKey", "iam:ListAccessKeys",
        "iam:PutUserPolicy", "iam:DeleteUserPolicy", "iam:GetUserPolicy",
        "iam:ListUserPolicies", "iam:TagUser", "iam:UntagUser"
      ],
      "Resource": [
        "arn:aws:iam::*:role/dev-fleet-telemetry-*",
        "arn:aws:iam::*:user/dev-fleet-telemetry-*",
        "arn:aws:iam::*:user/fleet-telemetry-*"
      ]
    }
  ]
}
```

---

## Day 1 Runbook

### A. Pre-Apply Checklist

| Item | Status |
|---|---|
| `fleet-telemetry-tfstate` S3 bucket exists | Done (Session 1) |
| `fleet-telemetry-tf-lock` DynamoDB table exists | Done (Session 1) |
| GitHub Secrets set (TF_AWS_ACCESS_KEY_ID, TF_AWS_SECRET_ACCESS_KEY) | Done (Session 1) |
| `lambda_function.py` real implementation written | **TODO** |
| `account_id` in `config.tfvars` set to real value | **TODO** |
| CI user Session 2 IAM permissions added | **TODO** |

Get account ID:
```bash
aws sts get-caller-identity --query Account --output text
```

### B. First Apply

```bash
cd infrastructure/environments/dev
terraform init
terraform fmt -check -recursive ../../
terraform validate
terraform plan -var-file=config.tfvars -out=tfplan
terraform apply tfplan
```

### C. Post-Apply Steps

```bash
# 1. Confirm SNS email — check inbox for srsawant.iu@gmail.com, click confirmation link

# 2. Retrieve Grafana credentials
terraform output -raw grafana_access_key_id
terraform output -raw grafana_secret_access_key

# 3. Set Grafana env vars in .env, then start Grafana
docker compose up -d

# 4. Run the fleet generator
export AWS_ACCESS_KEY_ID=$(terraform output -raw producer_access_key_id)
export AWS_SECRET_ACCESS_KEY=$(terraform output -raw producer_secret_access_key)
export AWS_DEFAULT_REGION=us-east-1
cd ../../..
python tools/fleet_generator.py

# 5. After ~90 s, trigger Glue crawler manually (first run only)
aws glue start-crawler --name dev-fleet-telemetry-crawler --region us-east-1
```

### D. Verify End-to-End

| Check | Expected |
|---|---|
| CloudWatch `/aws/lambda/dev-fleet-telemetry-detector` | "Anomalies found" log lines within 30 s |
| DynamoDB `dev-fleet-anomalies` | Items appear after ~25 iterations |
| Email inbox (`srsawant.iu@gmail.com`) | CRITICAL alert for coolant/RPM/DTC/signal anomalies |
| `aws s3 ls s3://dev-fleet-telemetry-lake-<ID>/raw/ --recursive` | `.json.gz` files after ~60 s |
| Athena: `SELECT * FROM dev_fleet_telemetry_db.raw LIMIT 10` | Rows after Glue crawler finishes |
| Grafana dashboard (localhost:3000) | Athena datasource connected, queries return data |

---

## Future Work (Session 3+)

| Item | Priority |
|---|---|
| Implement `src/rules_engine/app.py` (connect to Lambda or standalone) | Medium |
| Implement `src/timeout_watcher/app.py` (vehicle timeout detection) | Medium |
| Write unit tests in `tests/test_anomaly_rules.py` | Medium |
| Prod environment (`environments/prod/`) — full config, separate apply | Low |
| Grafana dashboards — fleet overview, anomaly heatmap, per-truck drill-down | Medium |
| Athena workgroup + cost controls | Low |
