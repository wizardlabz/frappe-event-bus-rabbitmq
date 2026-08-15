# Frappe Event Bus — RabbitMQ Provider

Publishes Event Bus messages to a RabbitMQ broker over AMQP, using [`pika`](https://pypi.org/project/pika/).

For an overview see the [README](../README.md). For core concepts — rules, templates, the outbox, retry — see the [core documentation](https://github.com/wizardlabz/frappe-event-bus/blob/main/docs/index.md).

## Contents

| | |
|---|---|
| [Installation](installation.md) | Install the provider alongside the core. |
| [Connection](connection.md) | How to reach a broker: host, credentials, TLS. |
| [Destination](destination.md) | What to publish and where: exchanges, queues, delivery options. |
| [Troubleshooting](troubleshooting.md) | Errors, causes, and fixes. |

## What this app contributes

Two doctypes and a publisher:

- **RabbitMQ Event Bus Connection** — broker coordinates and credentials.
- **RabbitMQ Event Bus Destination** — exchange, routing key, optional topology declaration, delivery options.
- **`RabbitMQPublisher`** — implements the core's provider contract.

It registers itself with the core through the standard hook:

```python
event_bus_providers = ["frappe_event_bus_rabbitmq.provider.get_provider"]
```

The registered provider name is **`rabbitmq`** — that is what you type into a rule destination's Provider field.

## How it fits the core

When a core Event Bus Rule fires with a destination whose provider is `rabbitmq`, the core renders the payload, writes an Outbox Message, and the background worker calls this provider. The publisher then:

1. Loads its own Connection and Destination documents from the names on the message.
2. Opens a `pika` connection.
3. Optionally declares the exchange, declares the queue, and binds them.
4. Publishes the rendered payload with `content_type: application/json`.
5. Returns a normalized success or failure result.
6. Closes the connection.

A fresh connection is opened per publish and closed afterwards. There is no connection pooling — a deliberate simplification for v0.1, appropriate for the volumes scheduled publishing produces.

The core owns everything else: retry scheduling, backoff, dead-lettering, replay, delivery logging, and retention. This app only decides *how to publish* and *whether a failure is worth retrying*.

## Failure classification

The single most consequential thing this provider does is tell the core whether a failure is transient:

| Classification | Cases |
|---|---|
| **Retryable** | Connection errors, timeouts, DNS failures, connection closed by broker |
| **Not retryable** | Authentication failures, broker channel errors (missing exchange, precondition failed), nacked or unroutable messages |

Anything unrecognised defaults to **retryable** and is logged for investigation — an unknown error is more likely transient than permanent, and a wrong guess here costs a delayed dead-letter rather than a lost message.

See [troubleshooting](troubleshooting.md) for what each error means in practice.

---

*This folder (`docs/`) is for documentation intended for end users. Internal notes and drafts live in `_local/`, which is gitignored and never published.*
