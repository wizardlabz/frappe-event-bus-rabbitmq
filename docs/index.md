# Frappe Event Bus — RabbitMQ Provider Documentation

End-user documentation for the RabbitMQ provider. For an overview and installation, see the [README](../README.md).

## RabbitMQ Event Bus Connection

Defines how to reach a broker. Fields: host, port (default 5672), virtual host (default `/`), username, **password** (stored encrypted), TLS enabled + verify, connection timeout, heartbeat. Use the **Test Connection** button to open and close a real connection and confirm the credentials work.

## RabbitMQ Event Bus Destination

Defines what to publish and where. Fields:

- **Exchange** + **Exchange Type** (`direct`, `fanout`, `topic`, `headers`)
- **Routing Key** (used unless a rule destination overrides it)
- **Declare Exchange / Durable Exchange** — declare the exchange on publish
- **Queue Name / Declare Queue / Durable Queue / Bind Queue** — optionally declare and bind a queue
- **Persistent Message** — `delivery_mode=2` so messages survive a broker restart
- **Publisher Confirms** — wait for broker acknowledgement; an unconfirmed/nacked publish is treated as a failure
- **Headers Template**

Use **Test Publish** to send a sample payload through the full path and view the broker response.

## How it fits the core

When a core Event Bus Rule fires with a destination whose provider is `rabbitmq`, the core writes an Outbox Message and the background worker calls this provider's publisher. The publisher loads its own Connection + Destination docs, opens a pika connection, optionally declares/binds topology, publishes the rendered payload, and returns the normalized success/failure result the core uses to drive retry/replay.

## Failure handling

- Authentication errors → **non-retryable** (the message is dead-lettered).
- Connection/timeout errors → **retryable** (the core reschedules with backoff).
- Unroutable / channel-precondition / nack → non-retryable.

## Troubleshooting

- *Connection refused / timeout* — check host/port reachability from the bench host and that the broker is up.
- *ACCESS_REFUSED* — wrong username/password or vhost permissions.
- *NOT_FOUND - no exchange* — enable **Declare Exchange** on the destination, or create the exchange on the broker.

---

*This folder (`docs/`) is for documentation intended for end users. Internal notes and drafts live in `_local/`, which is gitignored and never published.*
