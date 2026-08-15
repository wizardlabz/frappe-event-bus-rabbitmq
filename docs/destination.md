# RabbitMQ Event Bus Destination

Defines what to publish and where. Each destination belongs to one connection.

## Fields

| Field | Type | Default | Required | Purpose |
|---|---|---|---|---|
| `destination_name` | Data | — | yes | Primary key. |
| `connection` | Link | — | yes | The connection to publish over. |
| `exchange` | Data | — | yes¹ | Target exchange. |
| `exchange_type` | Select | `direct` | | `direct`, `fanout`, `topic`, or `headers`. |
| `routing_key` | Data | — | | Default routing key; a rule destination can override it. |
| `declare_exchange` | Check | `0` | | Declare the exchange before publishing. |
| `durable_exchange` | Check | `1` | | Declare it durable. Only applies when declaring. |
| `queue_name` | Data | — | ² | Queue to declare and/or bind. |
| `declare_queue` | Check | `0` | | Declare the queue before publishing. |
| `durable_queue` | Check | `1` | | Declare it durable. Only applies when declaring. |
| `bind_queue` | Check | `0` | | Bind the queue to the exchange with the routing key. |
| `persistent_message` | Check | `1` | | Publish with `delivery_mode=2`. |
| `publisher_confirms` | Check | `0` | | Wait for broker acknowledgement. |
| `headers_template` | Code (JSON) | — | | Default headers for everything published here. |
| `notes` | Small Text | — | | Free-text note. |

¹ Enforced by `validate_destination`, not by the doctype.
² Required when `declare_queue` or `bind_queue` is set.

## Exchange types

| Type | Routing behaviour |
|---|---|
| `direct` | Delivered to queues bound with exactly the routing key. |
| `fanout` | Delivered to every bound queue; routing key ignored. |
| `topic` | Pattern matching on dotted routing keys — `sales_order.#`. |
| `headers` | Matched on message headers instead of routing key. |

`exchange_type` is only used when `declare_exchange` is set. Publishing to an exchange that already exists uses whatever type the broker has; this field does not reconfigure it. Declaring with a type that disagrees with the existing exchange is a precondition failure, and is treated as non-retryable.

## Declaring topology

By default the provider declares nothing and assumes the exchange exists. The three declare/bind flags let it build topology on the fly, applied in this order:

1. `declare_exchange` → `exchange_declare(exchange, exchange_type, durable=durable_exchange)`
2. `declare_queue` → `queue_declare(queue_name, durable=durable_queue)`
3. `bind_queue` → `queue_bind(queue_name, exchange, routing_key)`

Declaration runs on **every publish**. It is idempotent when the parameters match what already exists, and fails when they do not.

Convenient for development and single-consumer setups. In production, prefer topology managed by your broker's own provisioning and leave these off — it avoids every publish carrying declaration overhead, and stops a misconfigured destination from creating unexpected queues.

## Delivery options

**`persistent_message`** (on by default) publishes with `delivery_mode=2`, so messages survive a broker restart — provided the queue is also durable. A persistent message on a non-durable queue is still lost when the broker restarts.

**`publisher_confirms`** (off by default) puts the channel into confirm mode and waits for the broker to acknowledge. A nacked or unroutable message then becomes a **non-retryable** failure and is dead-lettered.

Turning confirms on is the difference between "we handed it to the broker" and "the broker accepted responsibility for it". It costs a round trip per publish. For business events where a silent drop is unacceptable, that trade is usually worth making.

Every message is published with `content_type: application/json`.

## Headers

`headers_template` renders to a JSON object supplying **defaults** for everything published to this destination.

Its render context differs from the rule-level headers template. Here the only name in scope is `message`, the normalized message dict:

```jinja
{
  "x-source": "erpnext",
  "x-doctype": {{ message.reference_doctype | json }},
  "x-event": {{ message.event_type | json }}
}
```

Available keys on `message` include `reference_doctype`, `reference_name`, `event_type`, `routing_key`, `deduplication_key`, `connection`, `destination`, and `outbox_name`.

**Rule-level headers win on collision.** Headers set on the rule's destination row were rendered with full document context, making them the more specific configuration, so they override these defaults key by key.

A template that fails to render, or that produces JSON which is not an object, is ignored and logged. A misconfigured header never stops a message being delivered.

## Test Publish

**Test Publish** sends a one-off payload through the complete path — connect, declare topology, publish, close — and shows the normalized result. It does not create an Outbox Message or a Delivery Attempt, so a failure here leaves no trace in the core.

Note that without `publisher_confirms`, a successful test means the broker accepted the publish, not that any queue received it. Publishing to a `direct` exchange with a routing key nothing is bound to succeeds silently. Check the management UI, or enable confirms.

## Result shape

On success the provider returns:

```python
{
    "success": True,
    "provider_message_id": None,
    "response": {"exchange": "...", "routing_key": "...", "confirmed": True},
}
```

`provider_message_id` is always `None` — AMQP assigns no broker-side message id. If you need one, set it yourself in the payload or headers, for example from the rule's deduplication key.

## Validation

`validate_destination` checks configuration without contacting the broker:

- `exchange` is required.
- `queue_name` is required when `declare_queue` or `bind_queue` is set.

## Related

- [Connection](connection.md)
- [Troubleshooting](troubleshooting.md)
- [Core: destinations](https://github.com/wizardlabz/frappe-event-bus/blob/main/docs/concepts/destinations.md)
