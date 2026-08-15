"""The provider's whitelisted endpoints must authorize their caller.

``test_publish`` sends a real message to a real broker and ``test_connection``
decrypts the stored password to open a connection with it. Both are exposed
over ``/api/method/...`` to every authenticated user, so each has to check
permission itself — the desk hiding the button is not access control.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_event_bus_rabbitmq.frappe_event_bus_rabbitmq.doctype.rabbitmq_event_bus_connection.rabbitmq_event_bus_connection import (
	test_connection,
)
from frappe_event_bus_rabbitmq.frappe_event_bus_rabbitmq.doctype.rabbitmq_event_bus_destination.rabbitmq_event_bus_destination import (
	test_publish,
)

CONNECTION = "_Test EB Perm Connection"
DESTINATION = "_Test EB Perm Destination"
NOBODY = "_test_ebrmq_nobody@example.com"


def _ensure_user(email: str) -> None:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "EB RMQ Test",
				"send_welcome_email": 0,
				"roles": [{"role": "Blogger"}],
			}
		).insert(ignore_permissions=True)


class TestProviderApiPermissions(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_user(NOBODY)

	def setUp(self):
		frappe.set_user("Administrator")
		self._cleanup()
		frappe.get_doc(
			{
				"doctype": "RabbitMQ Event Bus Connection",
				"connection_name": CONNECTION,
				"enabled": 1,
				# Deliberately unreachable: the permission check must reject the
				# caller before any connection is attempted.
				"host": "203.0.113.1",
				"port": 5672,
				"virtual_host": "/",
				"username": "guest",
				"password": "guest",
				"connection_timeout": 1,
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "RabbitMQ Event Bus Destination",
				"destination_name": DESTINATION,
				"connection": CONNECTION,
				"exchange": "perm.test",
				"exchange_type": "direct",
				"routing_key": "perm.test",
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		self._cleanup()

	def _cleanup(self):
		frappe.delete_doc_if_exists("RabbitMQ Event Bus Destination", DESTINATION, force=1)
		frappe.delete_doc_if_exists("RabbitMQ Event Bus Connection", CONNECTION, force=1)

	def test_test_publish_rejects_an_unprivileged_caller(self):
		frappe.set_user(NOBODY)
		with self.assertRaises(frappe.PermissionError):
			test_publish(DESTINATION)

	def test_test_connection_rejects_an_unprivileged_caller(self):
		frappe.set_user(NOBODY)
		with self.assertRaises(frappe.PermissionError):
			test_connection(CONNECTION)

	def test_test_connection_still_reaches_the_broker_for_an_administrator(self):
		"""An authorized caller gets past the check and gets a real result."""
		result = test_connection(CONNECTION)
		# The host is unreachable, so this reports a connection failure rather
		# than raising PermissionError — proving the check let it through.
		self.assertFalse(result["success"])
		self.assertIn("error", result)
