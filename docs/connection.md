# RabbitMQ Event Bus Connection

Defines how to reach a broker. One connection is typically shared by many destinations.

## Fields

| Field | Type | Default | Required | Purpose |
|---|---|---|---|---|
| `connection_name` | Data | — | yes | Primary key. |
| `enabled` | Check | `1` | | Marks the connection as usable. |
| `host` | Data | — | yes | Broker hostname or IP. Falls back to `localhost` if blank at publish time. |
| `port` | Int | `5672` | | AMQP port. Use `5671` for TLS. |
| `virtual_host` | Data | `/` | | RabbitMQ vhost. |
| `username` | Data | — | | Falls back to `guest` when blank. |
| `password` | Password | — | | Stored **encrypted**. Falls back to `guest` when blank. |
| `tls_enabled` | Check | `0` | | Connect over TLS (AMQPS). |
| `tls_verify` | Check | `1` | | Verify the broker's certificate and hostname. |
| `connection_timeout` | Int | `30` | | Socket timeout in seconds. |
| `heartbeat` | Int | `60` | | AMQP heartbeat interval in seconds. |
| `notes` | Small Text | — | | Free-text note. |

## Credentials

`password` is a Frappe `Password` field, so it is encrypted at rest and never returned in plain text by the API. The publisher reads it through `get_password()` at publish time.

Leaving username and password blank falls back to `guest`/`guest`. That works for a local broker only — RabbitMQ restricts the `guest` account to loopback connections, so a remote broker needs a real user.

## TLS

Set `tls_enabled` to connect over AMQPS, and remember to change `port` to `5671`; enabling TLS does not change the port for you.

`tls_verify` is on by default and should stay on. Turning it off disables both certificate verification and hostname checking, which leaves the connection encrypted but unauthenticated — acceptable against a self-signed broker in development, not in production.

## Timeouts and heartbeat

`connection_timeout` bounds how long a publish attempt waits for a socket. Since the outbox worker processes a batch of messages in sequence, a long timeout against an unreachable broker slows the whole batch — keep it modest and let the core's retry handle transient outages.

`heartbeat` matters less here than for long-lived consumers, because the provider opens a connection per publish and closes it immediately after.

## Test Connection

The **Test Connection** button opens a real connection with these settings and closes it again. It contacts the broker; it does not publish anything.

On failure it reports the classified error — an authentication failure reads differently from a network failure, which is usually enough to identify the problem. See [troubleshooting](troubleshooting.md).

## Connection lifecycle

The publisher opens a fresh connection for each publish and closes it in a `finally` block, ignoring errors raised during teardown so a failure to close never masks the publish result.

There is no pooling or reuse. That is a deliberate v0.1 simplification suited to scheduled publishing volumes; it would be worth revisiting for a high-throughput dedicated worker.

## Related

- [Destination](destination.md) — what to publish, and where
- [Troubleshooting](troubleshooting.md)
