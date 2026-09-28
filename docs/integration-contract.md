# SaltMon Integration Contract — v1

The only interface between the `SaltMon-<env>` stack (this repo) and its consumers (ChoreCore's `softener`
feature). Normative source: `docs/requirements.md` §8.1 and §8.3. If the two differ, this document wins for
consumers, and the requirements must be corrected.

## 1. Discovery

| SSM parameter (us-east-1, account 345482189436) | Value |
|---|---|
| `/saltmon/<env>/readings-topic-arn` | ARN of SNS topic `SaltMon-<env>-readings` |
| `/saltmon/<env>/contract-version` | `1` |

Consumers resolve the ARN at synth or deploy time (`ssm.StringParameter.valueForStringParameter`). There are no
CloudFormation exports, so either stack can be redeployed independently. SaltMon must be deployed first.

## 2. Subscribing

- Standard SNS topic, SSE with a SaltMon customer-managed KMS key.
- Subscribe an **SQS queue** (with DLQ) in the same account, with **raw message delivery enabled**. The key policy
  already lets SNS encrypt into subscriber queues in this account. The consumer queue must use its own KMS key or
  SQS-managed SSE.
- Only principals in account `345482189436` may subscribe.
- Filter with message attributes if desired, e.g. `{"kind": ["forecast", "status", "event"]}`.

| Message attribute | Type | Values |
|---|---|---|
| `kind` | String | `telemetry`, `event`, `forecast`, `status` |
| `thing` | String | `saltmon-<6 hex>` |

## 3. Envelope

```json
{
  "contract": 1,
  "kind": "forecast",
  "thing": "saltmon-a1b2c3",
  "ts": 1790000000000,
  "received_at": 1790000000321,
  "data": { }
}
```

| Field | Type | Meaning |
|---|---|---|
| `contract` | int | Contract major version. Ignore messages with an unknown value. |
| `kind` | string | Selects the shape of `data`. |
| `thing` | string | IoT thing name. The consumer maps it to a family in its own config. |
| `ts` | int, epoch ms | Device time for `telemetry`/`event`, and compute time for `forecast`/`status`. |
| `received_at` | int, epoch ms | When SaltMon stored or produced the record. |
| `data` | object | Kind-specific, below. |

## 4. `data` by kind

### `telemetry` (every ~10 min)

| Field | Type | Notes |
|---|---|---|
| `schema` | int | Device schema, `1` |
| `seq` | int | Device sequence counter, resets on reboot |
| `distance_mm` | int \| null | Median of the valid samples; null if none |
| `distance_min_mm`, `distance_max_mm` | int \| null | |
| `valid`, `samples` | int | Valid and total sample count in the burst |
| `level_pct` | number \| null | 0–100, from `d_full_mm`/`d_low_mm` |
| `state` | string | `OK`, `REFILL`, `FAULT`, `OBSTRUCTED`, `UNCALIBRATED` |
| `bridge_suspected` | bool | Salt bridge hint |
| `temp_c` | number | US-100 temperature |
| `rssi_dbm` | int | |
| `uptime_s` | int | |
| `fw` | string | Semver |

### `event`

| Field | Type | Notes |
|---|---|---|
| `schema`, `seq` | int | |
| `type` | string | `boot`, `state_change`, `refill_detected`, `bridge_suspected`, `sensor_fault` |
| `from`, `to` | string \| null | States, for `state_change` |
| `detail` | string \| null | Free text |
| `reset_reason`, `fw` | string | `boot` only |

### `forecast` (hourly)

| Field | Type | Notes |
|---|---|---|
| `level_pct` | number | Latest hourly median |
| `rate_in_per_day` | number \| null | Salt height consumed per day |
| `rate_lb_per_day` | number \| null | At 10.3 lb/in |
| `refill_eta` | int \| null | Epoch ms when the level reaches `refill_pct` |
| `days_to_refill` | number \| null | 0 if already at or below `refill_pct` |
| `confidence` | string | `high`, `low`, `insufficient` (then ETA and rates are null) |
| `r2` | number \| null | |
| `points` | int | Hourly points used |

### `status` (transitions only)

| Field | Type | Notes |
|---|---|---|
| `online` | bool | false after > 1 h without telemetry |
| `last_seen` | int | Epoch ms of the last telemetry |

## 5. Delivery Semantics

- **At least once, unordered.** De-duplicate on (`thing`, `kind`, `ts`).
- Use `ts` to discard stale records (e.g. a late `forecast` older than the one stored).
- SaltMon publishes only records it stored for the first time, so duplicates come only from SNS/SQS retries.

## 6. Evolution

- Within `contract: 1`, fields are only **added**. Consumers must ignore unknown fields and unknown `kind`s.
- A breaking change bumps `contract`, is published side by side on a new topic, and gets a new SSM parameter.
  The v1 topic keeps running until every consumer has moved.

## 7. Consumer Obligations (ChoreCore)

- Read-only toward the device and SaltMon. No calls back into SaltMon in v1.
- The sensor never completes a chore (ChoreCore INV-01).
- Failed messages go to the DLQ; the consumer alarms on DLQ depth > 0.
