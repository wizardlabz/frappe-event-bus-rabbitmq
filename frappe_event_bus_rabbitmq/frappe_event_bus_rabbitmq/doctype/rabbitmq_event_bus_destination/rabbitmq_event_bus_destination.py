"""RabbitMQ Event Bus Destination controller."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.model.document import Document

from frappe_event_bus_rabbitmq.publisher import RabbitMQPublisher


class RabbitMQEventBusDestination(Document):
	"""A RabbitMQ exchange/queue target for published events."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		bind_queue: DF.Check
		connection: DF.Link
		declare_exchange: DF.Check
		declare_queue: DF.Check
		destination_name: DF.Data
		durable_exchange: DF.Check
		durable_queue: DF.Check
		exchange: DF.Data | None
		exchange_type: DF.Literal["direct", "fanout", "topic", "headers"]
		headers_template: DF.Code | None
		notes: DF.SmallText | None
		persistent_message: DF.Check
		publisher_confirms: DF.Check
		queue_name: DF.Data | None
		routing_key: DF.Data | None
	# end: auto-generated types

	def validate(self) -> None:
		"""Apply provider-side destination validation rules on save."""
		RabbitMQPublisher().validate_destination(self)


@frappe.whitelist()
def test_publish(destination_name: str, payload: str | None = None) -> dict[str, Any]:
	"""Publish a sample payload to the destination's broker.

	Args:
		destination_name: Name of the destination document.
		payload: Optional JSON string; a default sample is used when omitted.

	Returns:
		The normalized publish result from the publisher.
	"""
	destination = frappe.get_doc("RabbitMQ Event Bus Destination", destination_name)
	connection = frappe.get_doc("RabbitMQ Event Bus Connection", destination.connection)
	body = frappe.parse_json(payload) if payload else {"_test": True, "source": "test_publish"}
	return RabbitMQPublisher().test_publish(connection, destination, body)
