# Release Notes

All notable changes to the **Frappe Event Bus — RabbitMQ Provider** are recorded here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [Semantic Versioning](https://semver.org/). This app's **major** version tracks the core's: `1.x` supports `frappe_event_bus >=1.0,<2.0`.

Sections used: **Added**, **Changed**, **Deprecated**, **Removed**, **Fixed**, **Security**.

---

## [Unreleased]

Nothing yet.

---

## [0.1.0] — First provider *(not yet released)*

RabbitMQ as a publishing destination for [Frappe Event Bus](https://github.com/wizardlabz/frappe-event-bus), over AMQP via [`pika`](https://pypi.org/project/pika/).

### Added

**DocTypes**

- **RabbitMQ Event Bus Connection** — host, port, virtual host, username, encrypted password, TLS with optional verification, connection timeout, heartbeat. Includes a **Test Connection** action that opens and closes a real connection.
- **RabbitMQ Event Bus Destination** — exchange and exchange type (`direct`, `fanout`, `topic`, `headers`), routing key, optional exchange/queue declaration and binding, persistent messages, publisher confirms, and a headers template. Includes a **Test Publish** action that exercises the full path.

**Publishing**

- `RabbitMQPublisher` implementing the core's provider contract.
- Optional topology declaration on publish — declare exchange, declare queue, bind queue — so a destination can build what it needs without separate broker provisioning.
- **Persistent messages** (`delivery_mode=2`) on by default; every message carries `content_type: application/json`.
- **Publisher confirms**, off by default, turning an unroutable or nacked message into a non-retryable failure rather than a silent drop.
- TLS support with optional certificate and hostname verification.
- **Destination headers template** supplying defaults for everything published to a destination, rendered with the normalized `message` in scope. Rule-level headers override these on collision, having been rendered with full document context. A headers template that fails to render is logged and ignored rather than blocking delivery.

**Failure classification**

- `classify_failure`, a pure function mapping a `pika` exception to `(message, retryable)` and unit-testable without a broker:
  - **Non-retryable** — authentication failures, broker channel errors (missing exchange, precondition failed), nacked or unroutable messages.
  - **Retryable** — connection errors, timeouts, DNS and socket failures.
  - Anything unrecognised defaults to retryable and is logged for investigation.
- Authentication is checked before connection errors, because `ProbableAuthenticationError` subclasses `AMQPConnectionError` — the other order would treat a bad password as transient and spend the whole attempt budget on it.

**Project**

- `before_install` check that fails clearly when the core app is missing, rather than later with an import error.
- CI running a real `rabbitmq:3-management` service container alongside a real Frappe stack. Integration tests deliberately do **not** skip when the broker is unreachable — a silent skip would report green on a broken CI broker.
- Full documentation under [`docs/`](docs/index.md).

### Security

- **Both whitelisted endpoints now authorize their caller.** Neither checked anything, and both are reachable over `/api/method/...` by any authenticated user.

  `test_publish` was the more serious: it takes a caller-supplied body and sends it as a real message to a real broker, so any signed-in user could publish arbitrary payloads to whatever a destination points at — reaching systems well outside Frappe. `test_connection` decrypts the stored password to open a connection with it, and its result reveals whether a host is reachable.

  Both now require read permission on the documents they use, checked before any broker contact. `test_publish` checks the destination and then the connection it resolves to, so a caller cannot reach a connection indirectly through a destination they can see.

### Notes and limitations

- **`provider_message_id` is always `None`.** AMQP assigns no broker-side message id; set one yourself in the payload or headers if you need it.
- **A connection is opened per publish and closed afterwards.** There is no pooling — a deliberate simplification suited to scheduled publishing volumes, revisited alongside the core's dedicated worker mode.
- **Topology declaration runs on every publish** and is idempotent only when every parameter matches the existing object. Prefer externally provisioned topology in production.
- **No consumer.** Inbound RabbitMQ arrives with the core's consumer foundation in 0.3.0.

[Unreleased]: https://github.com/wizardlabz/frappe-event-bus-rabbitmq/compare/main...HEAD
[0.1.0]: https://github.com/wizardlabz/frappe-event-bus-rabbitmq/releases/tag/v0.1.0
