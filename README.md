# Frappe Event Bus — RabbitMQ Provider

> RabbitMQ provider for [Frappe Event Bus](https://github.com/wizardlabz/frappe-event-bus).

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Status: early development](https://img.shields.io/badge/status-early%20development-orange.svg)](#status)

This app adds **RabbitMQ** as a publishing destination for [Frappe Event Bus](https://github.com/wizardlabz/frappe-event-bus). It contributes RabbitMQ-specific connection and destination DocTypes and a publisher that delivers outbox messages to a broker over AMQP (via [`pika`](https://pypi.org/project/pika/)).

It is a standalone Frappe app that **depends on the core** `frappe_event_bus` app and registers itself with the core's provider registry.

## Status

🚧 **Early development.** Scaffolding is in place; the connection/destination DocTypes and publisher are being built. Not yet ready for production.

## Planned capabilities

- Publish to `direct` / `fanout` / `topic` / `headers` exchanges
- Routing keys, custom headers, persistent (durable) messages
- Optional exchange/queue declaration and binding
- TLS connections
- Publisher confirms
- Test connection & test publish
- Retryable vs. non-retryable failure classification

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
