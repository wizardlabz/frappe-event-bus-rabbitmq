"""Provider spec contributed to the Frappe Event Bus core via the hook."""

from __future__ import annotations

from typing import Any


def get_provider() -> dict[str, Any]:
	"""Return the RabbitMQ provider spec for the core registry."""
	return {
		"name": "rabbitmq",
		"label": "RabbitMQ",
		"connection_doctype": "RabbitMQ Event Bus Connection",
		"destination_doctype": "RabbitMQ Event Bus Destination",
		"publisher": "frappe_event_bus_rabbitmq.publisher.RabbitMQPublisher",
	}
