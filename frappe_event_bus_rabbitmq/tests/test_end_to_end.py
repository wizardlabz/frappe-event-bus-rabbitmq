"""The whole publishing chain, against a real broker.

Every other test in this app exercises one link: the publisher is called with a
hand-built message dict, or the core's rule engine is driven with a fake
provider. Nothing asserted that a document saved in Frappe actually arrives on a
queue, which is the only claim a user cares about.

This drives the real path end to end::

    ToDo saved
      -> rule matched          (core rule engine, via the doc_events hook)
      -> payload rendered      (core Jinja template)
      -> Outbox Message written
      -> worker claims and publishes
      -> RabbitMQ publisher opens a real connection
      -> message read back off a real queue

A break in any link fails this test, which is the point: the unit tests on
either side would all still pass.

Like the other integration tests here, this does **not** skip when the broker is
unreachable. A silent skip reports green on a broken CI broker.
"""

from __future__ import annotations

import json
import os
import uuid

import frappe
import pika
from frappe.tests.utils import FrappeTestCase
from frappe_event_bus.publisher.outbox_worker import process_pending

BROKER_HOST = os.environ.get("RABBITMQ_TEST_HOST", "rabbitmq")
BROKER_PORT = int(os.environ.get("RABBITMQ_TEST_PORT", "5672"))
BROKER_USER = os.environ.get("RABBITMQ_TEST_USER", "guest")
BROKER_PASS = os.environ.get("RABBITMQ_TEST_PASS", "guest")


def _enable_bus() -> None:
	settings = frappe.get_doc("Event Bus Settings")
	settings.enabled = 1
	settings.save(ignore_permissions=True)
	frappe.clear_document_cache("Event Bus Settings", "Event Bus Settings")


def _broker_channel() -> tuple[pika.BlockingConnection, object]:
	"""Open an independent connection, so nothing is shared with the publisher."""
	connection = pika.BlockingConnection(
		pika.ConnectionParameters(
			host=BROKER_HOST,
			port=BROKER_PORT,
			virtual_host="/",
			credentials=pika.PlainCredentials(BROKER_USER, BROKER_PASS),
			socket_timeout=5,
		)
	)
	return connection, connection.channel()


class TestPublishingEndToEnd(FrappeTestCase):
	"""A document event in Frappe reaches a queue in RabbitMQ."""

	def setUp(self) -> None:
		self.suffix = uuid.uuid4().hex[:8]
		self.exchange = f"_test_e2e_ex_{self.suffix}"
		self.queue = f"_test_e2e_q_{self.suffix}"
		self.template_name = f"_test_e2e_tmpl_{self.suffix}"
		self.rule_name = f"_test_e2e_rule_{self.suffix}"

		_enable_bus()

		self.connection_doc = frappe.get_doc(
			{
				"doctype": "RabbitMQ Event Bus Connection",
				"connection_name": f"_test_e2e_conn_{self.suffix}",
				"enabled": 1,
				"host": BROKER_HOST,
				"port": BROKER_PORT,
				"virtual_host": "/",
				"username": BROKER_USER,
				"password": BROKER_PASS,
				"connection_timeout": 5,
				"heartbeat": 30,
			}
		).insert(ignore_permissions=True)

		# bind_queue is deliberately off. The publisher binds using whatever
		# routing key the message carries, so letting it bind would make the queue
		# match by construction and this test could never catch a routing
		# misconfiguration. The binding is fixed in setUp instead.
		self.destination_doc = frappe.get_doc(
			{
				"doctype": "RabbitMQ Event Bus Destination",
				"destination_name": f"_test_e2e_dest_{self.suffix}",
				"connection": self.connection_doc.name,
				"exchange": self.exchange,
				"exchange_type": "direct",
				"routing_key": "todo.created",
				"declare_exchange": 1,
				"durable_exchange": 0,
				"queue_name": self.queue,
				"declare_queue": 1,
				"durable_queue": 0,
				"bind_queue": 0,
				"persistent_message": 1,
				"publisher_confirms": 1,
			}
		).insert(ignore_permissions=True)

		frappe.get_doc(
			{
				"doctype": "Event Bus Message Template",
				"template_name": self.template_name,
				"enabled": 1,
				"jinja_template": (
					'{"id": {{ doc.name | json }}, '
					'"description": {{ doc.description | json }}, '
					'"event": {{ context.event_type | json }}}'
				),
			}
		).insert(ignore_permissions=True)

		frappe.get_doc(
			{
				"doctype": "Event Bus Rule",
				"rule_name": self.rule_name,
				"enabled": 1,
				"reference_doctype": "ToDo",
				"event_type": "after_insert",
				"message_template": self.template_name,
				"destinations": [
					{
						"enabled": 1,
						"provider": "rabbitmq",
						"connection": self.connection_doc.name,
						"destination": self.destination_doc.name,
						"routing_key": "todo.created",
					}
				],
			}
		).insert(ignore_permissions=True)

		# Declare the topology up front rather than relying on the publisher to
		# create it. Otherwise a test asserting that nothing was published would
		# find no queue at all and pass for the wrong reason — "the queue is
		# empty" and "the queue was never created" are very different claims.
		# Parameters match the destination's exactly, so its own declaration on
		# publish is a no-op rather than a precondition failure.
		self._declare_broker_topology()

	def _declare_broker_topology(self) -> None:
		connection, channel = _broker_channel()
		try:
			channel.exchange_declare(exchange=self.exchange, exchange_type="direct", durable=False)
			channel.queue_declare(queue=self.queue, durable=False)
			channel.queue_bind(queue=self.queue, exchange=self.exchange, routing_key="todo.created")
		finally:
			connection.close()

	def tearDown(self) -> None:
		frappe.db.delete("Event Bus Outbox Message", {"event_rule": self.rule_name})
		frappe.delete_doc_if_exists("Event Bus Rule", self.rule_name, force=1)
		frappe.delete_doc_if_exists("Event Bus Message Template", self.template_name, force=1)
		self._tear_down_broker_topology()

	def _tear_down_broker_topology(self) -> None:
		"""Remove the queue and exchange this test declared.

		Failures here are ignored: an unreachable broker is the assertion's
		problem, not the cleanup's, and masking the real failure with a
		teardown error would make the run harder to read.
		"""
		try:
			connection, channel = _broker_channel()
			try:
				channel.queue_delete(queue=self.queue)
				channel.exchange_delete(exchange=self.exchange)
			finally:
				connection.close()
		except Exception:
			pass

	def _read_one_from_queue(self) -> tuple[dict, object] | tuple[None, None]:
		"""Fetch a single message off the queue, or (None, None) if empty."""
		connection, channel = _broker_channel()
		try:
			method, properties, body = channel.basic_get(queue=self.queue, auto_ack=True)
			if method is None:
				return None, None
			return json.loads(body.decode()), properties
		finally:
			connection.close()

	def test_a_saved_document_arrives_on_the_queue(self) -> None:
		todo = frappe.get_doc({"doctype": "ToDo", "description": f"end to end {self.suffix}"}).insert(
			ignore_permissions=True
		)

		# The rule engine writes the outbox row synchronously, inside the same
		# transaction as the document.
		outbox = frappe.get_all(
			"Event Bus Outbox Message",
			filters={"event_rule": self.rule_name, "reference_document": todo.name},
			fields=["name", "status", "provider", "routing_key"],
		)
		self.assertEqual(len(outbox), 1, "the rule should write exactly one outbox row")
		self.assertEqual(outbox[0].status, "Pending")
		self.assertEqual(outbox[0].provider, "rabbitmq")

		# Publishing is normally enqueued after commit; drive it directly.
		counts = process_pending(batch_size=10)
		self.assertGreaterEqual(counts["published"], 1)

		self.assertEqual(
			frappe.db.get_value("Event Bus Outbox Message", outbox[0].name, "status"),
			"Published",
		)

		payload, properties = self._read_one_from_queue()
		self.assertIsNotNone(payload, "no message arrived on the queue")
		self.assertEqual(payload["id"], todo.name)
		self.assertEqual(payload["description"], f"end to end {self.suffix}")
		self.assertEqual(payload["event"], "after_insert")

		# Delivery options configured on the destination must survive the trip.
		self.assertEqual(properties.content_type, "application/json")
		self.assertEqual(properties.delivery_mode, 2, "persistent_message was set")

	def test_a_delivery_attempt_records_the_successful_publish(self) -> None:
		todo = frappe.get_doc({"doctype": "ToDo", "description": f"attempt log {self.suffix}"}).insert(
			ignore_permissions=True
		)
		outbox_name = frappe.get_all(
			"Event Bus Outbox Message",
			filters={"event_rule": self.rule_name, "reference_document": todo.name},
			pluck="name",
		)[0]

		process_pending(batch_size=10)

		attempts = frappe.get_all(
			"Event Bus Delivery Attempt",
			filters={"outbox_message": outbox_name},
			fields=["attempt_number", "success", "provider", "provider_response"],
		)
		self.assertEqual(len(attempts), 1)
		self.assertEqual(attempts[0].attempt_number, 1)
		self.assertTrue(attempts[0].success)
		self.assertEqual(attempts[0].provider, "rabbitmq")

		response = json.loads(attempts[0].provider_response)
		self.assertEqual(response["exchange"], self.exchange)
		self.assertEqual(response["routing_key"], "todo.created")
		self.assertTrue(response["confirmed"], "publisher_confirms was set")

	def test_a_condition_that_does_not_match_publishes_nothing(self) -> None:
		"""The chain must stay silent when the rule's condition rejects the doc."""
		frappe.db.set_value(
			"Event Bus Rule", self.rule_name, "condition", "doc.description == 'never matches'"
		)
		frappe.clear_document_cache("Event Bus Rule", self.rule_name)

		todo = frappe.get_doc({"doctype": "ToDo", "description": f"filtered out {self.suffix}"}).insert(
			ignore_permissions=True
		)

		self.assertEqual(
			frappe.db.count(
				"Event Bus Outbox Message",
				{"event_rule": self.rule_name, "reference_document": todo.name},
			),
			0,
		)

		process_pending(batch_size=10)
		payload, _ = self._read_one_from_queue()
		self.assertIsNone(payload, "a non-matching condition must publish nothing")
