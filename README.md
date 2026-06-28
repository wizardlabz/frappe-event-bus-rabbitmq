# Frappe Event Bus — RabbitMQ Provider

> RabbitMQ provider for [Frappe Event Bus](https://github.com/wizardlabz/frappe-event-bus).

[![CI](https://github.com/wizardlabz/frappe-event-bus-rabbitmq/actions/workflows/ci.yml/badge.svg)](https://github.com/wizardlabz/frappe-event-bus-rabbitmq/actions/workflows/ci.yml)
[![Linter](https://github.com/wizardlabz/frappe-event-bus-rabbitmq/actions/workflows/linter.yml/badge.svg)](https://github.com/wizardlabz/frappe-event-bus-rabbitmq/actions/workflows/linter.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

This app adds **RabbitMQ** as a publishing destination for [Frappe Event Bus](https://github.com/wizardlabz/frappe-event-bus). It contributes RabbitMQ-specific connection and destination DocTypes and a publisher that delivers outbox messages to a broker over AMQP (via [`pika`](https://pypi.org/project/pika/)).

It is a standalone Frappe app that **depends on the core** `frappe_event_bus` app and registers itself with the core's provider registry.

## Status

**v0.1 — implemented and tested.** Connection + Destination DocTypes, the pika-based publisher, validation, registration, and the core-dependency guard are built and covered by an automated suite (20 tests, including integration tests against a live RabbitMQ broker). APIs may still change before 1.0.

## Capabilities

- Publish to `direct` / `fanout` / `topic` / `headers` exchanges
- Routing keys, custom headers, persistent (durable) messages
- Optional exchange/queue declaration and binding
- TLS connections (with optional certificate verification)
- Publisher confirms
- **Test Connection** and **Test Publish** buttons on the DocTypes
- Retryable vs. non-retryable failure classification (auth → non-retryable, connection → retryable), so the core's retry/replay behaves correctly

## Installation

Install the **core app first**, then this provider:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/wizardlabz/frappe-event-bus --branch main
bench get-app https://github.com/wizardlabz/frappe-event-bus-rabbitmq --branch main

bench --site <your-site> install-app frappe_event_bus
bench --site <your-site> install-app frappe_event_bus_rabbitmq
bench --site <your-site> migrate
```

Installing this provider without the core app installed will fail with a clear error.

## Contributing

This app uses `pre-commit` (ruff, eslint, prettier, pyupgrade). After cloning:

```bash
cd apps/frappe_event_bus_rabbitmq
pre-commit install
```

## License

[GPL-3.0](license.txt) © WizardLabz
