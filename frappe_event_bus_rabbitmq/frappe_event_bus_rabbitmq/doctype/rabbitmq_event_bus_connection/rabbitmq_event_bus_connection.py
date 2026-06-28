"""RabbitMQ Event Bus Connection controller."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.model.document import Document

from frappe_event_bus_rabbitmq.publisher import RabbitMQPublisher


class RabbitMQEventBusConnection(Document):
	"""Connection parameters for a RabbitMQ broker."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		connection_timeout: DF.Int
		connection_name: DF.Data
		enabled: DF.Check
		heartbeat: DF.Int
		host: DF.Data
		notes: DF.SmallText | None
		password: DF.Password | None
		port: DF.Int
		tls_enabled: DF.Check
		tls_verify: DF.Check
		username: DF.Data | None
		virtual_host: DF.Data | None
	# end: auto-generated types


@frappe.whitelist()
def test_connection(connection_name: str) -> dict[str, Any]:
	"""Open and close a broker connection to verify the settings.

	Returns:
		``{"success": True}`` on success, otherwise ``{"success": False,
		"error": <message>}``.
	"""
	doc = frappe.get_doc("RabbitMQ Event Bus Connection", connection_name)
	try:
		RabbitMQPublisher().validate_connection(doc)
		return {"success": True, "message": frappe._("Connection successful.")}
	except frappe.ValidationError as exc:
		return {"success": False, "error": str(exc)}
