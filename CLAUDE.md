# Fleet Telemetry — Project Context

## What this is
Standalone fleet tracking system. Independent of all other projects.
25-truck Python simulator (`tools/fleet_generator.py`) runs locally,
pushes telemetry to AWS Kinesis every second for 1000 iterations.
Trucks span 10 US regions with 7 anomaly profiles.

## Session history
- **Session 1** (complete): Provisioned Kinesis stream + IAM producer user via Terraform.
  CI wired to develop branch via GitHub Actions. Remote state (S3 + DynamoDB) set up manually.
- **Session 2** (code written, not yet deployed): Added 7 Terraform modules for S3, Firehose,
  Glue, DynamoDB, SNS, Lambda detector, and Grafana IAM user. All infra code is ready.
  Lambda function placeholder exists but needs real implementation before `terraform apply`.

## Current infrastructure (dev) — Deployed (Session 1)
- Kinesis Data Stream: `fleet-telemetry-stream`
    Region:     us-east-1
    Mode:       PROVISIONED
    Shards:     1
    Retention:  24 hours
    Partition:  by VIN

- IAM producer user: `fleet-telemetry-producer`
    Access:     Programmatic only (no console)
    Policy:     Inline, scoped to stream ARN
    Actions:    kinesis:PutRecord, PutRecords, DescribeStream, DescribeStreamSummary

- Remote state (pre-existing, NOT managed by Terraform):
    S3 bucket:      fleet-telemetry-tfstate
    DynamoDB table: fleet-telemetry-tf-lock
    Region:         us-east-1
    State key:      fleet-telemetry/terraform.tfstate

## Pending infrastructure (dev) — Code written, NOT applied (Session 2)
- S3 data lake:   `dev-fleet-telemetry-lake-<ACCOUNT_ID>` (lifecycle: IA→Glacier→expire)
- Firehose:       `dev-fleet-telemetry-raw-delivery` (Kinesis→S3, dynamic partition by fleet_group)
- Glue:           `dev_fleet_telemetry_db` database + JSON classifier + hourly crawler
- DynamoDB:       `dev-fleet-anomalies` (VIN+timestamp key, severity GSI, TTL 90 days)
- Lambda:         `dev-fleet-telemetry-detector` (Kinesis ESM, 5 anomaly checks, DynamoDB+SNS writes)
- SNS:            `dev-fleet-telemetry-alerts` (email: srsawant.iu@gmail.com)
- Grafana user:   `dev-fleet-telemetry-grafana` (read-only Athena/Glue/S3 policy)

## Terraform layout
```
infrastructure/
  environments/
    dev/
      main.tf          <- 11 module calls (kinesis, iam + 9 Session 2 modules)
      variables.tf     <- includes alert_email, account_id
      outputs.tf       <- stream_arn, keys, s3 bucket, dynamodb table, sns arn, grafana keys
      backend.tf       <- S3 + DynamoDB remote state config
      config.tfvars    <- dev var values (account_id = <YOUR_ACCOUNT_ID> — NEEDS REPLACEMENT)
    prod/
      config.tfvars    <- stub only (environment = "prod"), not ready
  modules/
    kinesis/           <- aws_kinesis_stream
    iam/               <- aws_iam_user, aws_iam_access_key, aws_iam_user_policy
    s3_datalake/       <- S3 bucket, public access block, SSE, lifecycle policies
    sns/               <- SNS topic + email subscription
    dynamodb/          <- DynamoDB table + GSI + TTL
    firehose/          <- Firehose delivery stream + IAM role
    glue/              <- Glue DB + classifier + crawler + IAM role
    lambda_detector/   <- Lambda function + Kinesis ESM + CloudWatch log group + IAM role
    grafana_user/      <- IAM user + access key + read-only Athena/Glue/S3 policy
  lambda_src/
    lambda_function.py <- PLACEHOLDER — must be replaced with real implementation before apply
```

## Lambda function spec (what needs implementing)
File: `infrastructure/lambda_src/lambda_function.py`

The handler must:
1. Decode Kinesis base64 records → JSON telemetry payloads
2. Run 5 anomaly checks per record:
   - `coolant_temp_c > 105.0` → CRITICAL, type=overheat
   - `engine_rpm > 6500` → CRITICAL, type=high_rpm
   - `active_dtc_codes` non-empty → CRITICAL, type=dtc_fault
   - `fuel_level_percent < 10.0` → WARN, type=low_fuel
   - `cell_signal_dbm < -95` → CRITICAL, type=signal_loss
3. Write anomalies to DynamoDB (vin, timestamp, severity, anomaly_type, value, fleet_group, ttl)
4. Publish CRITICAL anomalies to SNS
5. Return `batchItemFailures` list for partial batch error handling

Env vars injected: DYNAMODB_TABLE, SNS_TOPIC_ARN, ENVIRONMENT, ANOMALY_TTL_DAYS

## CI
`.github/workflows/terraform-dev.yml`
- Scoped to develop branch only, paths: `infrastructure/**`
- PR to develop → terraform plan (posted as PR comment)
- Push to develop → terraform apply -auto-approve
- GitHub Secrets: TF_AWS_ACCESS_KEY_ID, TF_AWS_SECRET_ACCESS_KEY

CI IAM user permissions (Session 1 — applied):
- kinesis:* on stream ARN
- iam: create/delete/get user, access key, user policy
- s3: GetObject, PutObject, ListBucket on tfstate bucket
- dynamodb: GetItem, PutItem, DeleteItem on lock table

CI IAM user permissions (Session 2 — **NOT YET ADDED**, see PLAN.md):
- s3: CreateBucket, DeleteBucket, public access block, encryption, lifecycle, tagging on `dev-fleet-telemetry-lake-*`
- sns: CreateTopic, DeleteTopic, Subscribe, Unsubscribe, GetTopicAttributes on `dev-fleet-telemetry-alerts`
- dynamodb: CreateTable, DeleteTable, DescribeTable, TTL, tags on `dev-fleet-anomalies`
- firehose: CreateDeliveryStream, DeleteDeliveryStream, DescribeDeliveryStream on `dev-fleet-telemetry-raw-delivery`
- glue: CreateDatabase, CreateCrawler, CreateClassifier, etc. (resource: *)
- lambda: CreateFunction, UpdateFunctionCode, CreateEventSourceMapping, etc. on `dev-fleet-telemetry-detector`
- logs: CreateLogGroup, PutRetentionPolicy, tags on `/aws/lambda/dev-fleet-telemetry-detector`
- iam: CreateRole, AttachRolePolicy, PutRolePolicy, PassRole on `dev-fleet-telemetry-*` roles/users

## Conventions
- Tags on every resource: Project=fleet-telemetry, Environment, ManagedBy=terraform
  (applied via `default_tags` on the AWS provider in dev/main.tf since Session 2)
- Least-privilege IAM — no wildcards except Glue (no resource-level support)
- Sensitive outputs marked `sensitive = true`
- New environments → new directory under `environments/`
- New AWS services → new module under `modules/`
- Every session ends with CLAUDE.md updated to reflect what was built

## Pre-deploy TODO (blocking `terraform apply`)
1. Implement `infrastructure/lambda_src/lambda_function.py` (see spec above)
2. Set `account_id` in `infrastructure/environments/dev/config.tfvars`
   (`aws sts get-caller-identity --query Account --output text`)
3. Add Session 2 CI IAM permissions to the CI IAM user (full JSON in PLAN.md)

## Post-deploy steps (after first apply)
1. Confirm SNS subscription email (check inbox, click confirmation link)
2. Retrieve Grafana credentials: `terraform output -raw grafana_access_key_id`
3. Set Grafana env vars in `.env` and start: `docker compose up -d`
4. Run fleet generator to produce test data: `python tools/fleet_generator.py`
5. Trigger first Glue crawl manually: `aws glue start-crawler --name dev-fleet-telemetry-crawler`

## Remaining application work (after deploy)
- `src/rules_engine/app.py` — currently a 3-line stub, not connected to Lambda
- `src/timeout_watcher/app.py` — empty placeholder for vehicle timeout detection
- `tests/test_anomaly_rules.py` — empty, no unit tests written yet
- Prod environment — `environments/prod/` stub only, full config needed
