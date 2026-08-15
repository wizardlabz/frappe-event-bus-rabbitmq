# Installation

## Requirements

- A Frappe **v15** bench
- The [`frappe_event_bus`](https://github.com/wizardlabz/frappe-event-bus) core app, installed first
- A reachable RabbitMQ broker
- `pika>=1.3,<2` — installed automatically with this app

## Install

```bash
cd $PATH_TO_YOUR_BENCH

# core first
bench get-app https://github.com/wizardlabz/frappe-event-bus --branch main
bench --site <your-site> install-app frappe_event_bus

# then this provider
bench get-app https://github.com/wizardlabz/frappe-event-bus-rabbitmq --branch main
bench --site <your-site> install-app frappe_event_bus_rabbitmq

bench --site <your-site> migrate
bench restart
```

The provider checks for the core during `before_install` and stops with a clear message if it is missing, rather than failing later with an import error:

> Please install Frappe Event Bus before installing this provider.

You can install this provider onto a site that already runs the core — no core reinstall or reconfiguration is needed.

## Verify

```bash
bench --site <your-site> console
```

```python
from frappe_event_bus.providers.registry import get_providers
get_providers()
```

You should see:

```python
{'rabbitmq': {
    'name': 'rabbitmq',
    'label': 'RabbitMQ',
    'connection_doctype': 'RabbitMQ Event Bus Connection',
    'destination_doctype': 'RabbitMQ Event Bus Destination',
    'publisher': 'frappe_event_bus_rabbitmq.publisher.RabbitMQPublisher',
}}
```

An empty dict means the hook is not being picked up — run `bench --site <your-site> migrate && bench restart`.

## A broker for local development

```bash
docker run -d --name rabbitmq \
  -p 5672:5672 -p 15672:15672 \
  rabbitmq:3-management
```

The management UI is at <http://localhost:15672> with `guest` / `guest`. It is the fastest way to confirm a message actually arrived.

Note that RabbitMQ's `guest` account is restricted to `localhost` connections by default. Connecting from another host or container needs a real user.

## Next

1. Create a [Connection](connection.md) and press **Test Connection**.
2. Create a [Destination](destination.md) and press **Test Publish**.
3. Reference both from a rule destination in the core, with Provider set to `rabbitmq`.

## Version compatibility

Keep the provider's major version aligned with the core's:

```
frappe_event_bus_rabbitmq 1.2.0 supports frappe_event_bus >=1.0,<2.0
```
