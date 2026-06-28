"""Integration tests against a real RabbitMQ broker.

These tests require a broker reachable at the host given by the
``RABBITMQ_TEST_HOST`` env var (default ``rabbitmq``, the docker-compose service
name) on port 5672, vhost ``/``, guest/guest. They are NOT skipped when the
broker is missing: a connectivity failure surfaces as an explicit failure of the
"happy path" assertions. In CI the broker runs as a service on ``localhost``.
"""

from __future__ import annotations

import os
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_event_bus_rabbitmq.publisher import RabbitMQPublisher

BROKER_HOST = os.environ.get("RABBITMQ_TEST_HOST", "rabbitmq")
BROKER_PORT = int(os.environ.get("RABBITMQ_TEST_PORT", "5672"))
BROKER_USER = os.environ.get("RABBITMQ_TEST_USER", "guest")
BROKER_PASS = os.environ.get("RABBITMQ_TEST_PASS", "guest")


def _make_connection(name: str, **overrides: object) -> frappe.model.document.Document:
	values = {
		"doctype": "RabbitMQ Event Bus Connection",
		"connection_name": name,
		"enabled": 1,
		"host": BROKER_HOST,
		"port": BROKER_PORT,
		"virtual_host": "/",
		"username": BROKER_USER,
		"password": BROKER_PASS,
		"connection_timeout": 5,
		"heartbeat": 30,
	}
	values.update(overrides)
	doc = frappe.get_doc(values)
	doc.insert(ignore_permissions=True)
	return doc


def _make_destination(name: str, connection: str, **overrides: object):
	values = {
		"doctype": "RabbitMQ Event Bus Destination",
		"destination_name": name,
		"connection": connection,
		"exchange": f"_test_ex_{uuid.uuid4().hex[:8]}",
		"exchange_type": "fanout",
		"routing_key": "",
		"declare_exchange": 1,
		"durable_exchange": 0,
		"persistent_message": 1,
		"publisher_confirms": 1,
	}
	values.update(overrides)
	doc = frappe.get_doc(values)
	doc.insert(ignore_permissions=True)
	return doc


class TestRabbitMQIntegration(FrappeTestCase):
	"""Exercises real publishing against the broker."""

	def setUp(self) -> None:
		self.publisher = RabbitMQPublisher()
		self.suffix = uuid.uuid4().hex[:8]

	def test_publish_success(self) -> None:
		conn = _make_connection(f"_t_conn_ok_{self.suffix}")
		dest = _make_destination(f"_t_dest_ok_{self.suffix}", conn.name)
		message = {
			"outbox_name": "OB-1",
			"provider": "rabbitmq",
			"connection": conn.name,
			"destination": dest.name,
			"routing_key": None,
			"payload": {"hello": "world"},
			"payload_json": frappe.as_json({"hello": "world"}),
			"headers": {"x-test": "1"},
			"reference_doctype": "User",
			"reference_name": "Administrator",
			"event_type": "after_insert",
			"deduplication_key": None,
		}
		result = self.publisher.publish(message)
		self.assertTrue(result["success"], msg=result)
		self.assertIn("response", result)

	def test_test_publish_success(self) -> None:
		conn = _make_connection(f"_t_conn_tp_{self.suffix}")
		dest = _make_destination(f"_t_dest_tp_{self.suffix}", conn.name)
		result = self.publisher.test_publish(conn, dest, {"sample": True})
		self.assertTrue(result["success"], msg=result)

	def test_bad_host_is_retryable_failure(self) -> None:
		conn = _make_connection(f"_t_conn_badhost_{self.suffix}", host="nonexistent-broker-host", port=5672)
		dest = _make_destination(f"_t_dest_badhost_{self.suffix}", conn.name)
		message = {
			"connection": conn.name,
			"destination": dest.name,
			"routing_key": None,
			"payload_json": "{}",
			"headers": {},
		}
		result = self.publisher.publish(message)
		self.assertFalse(result["success"])
		self.assertTrue(result["retryable"])

	def test_bad_credentials_is_not_retryable(self) -> None:
		conn = _make_connection(f"_t_conn_badcreds_{self.suffix}", username="baduser", password="badpass")
		dest = _make_destination(f"_t_dest_badcreds_{self.suffix}", conn.name)
		message = {
			"connection": conn.name,
			"destination": dest.name,
			"routing_key": None,
			"payload_json": "{}",
			"headers": {},
		}
		result = self.publisher.publish(message)
		self.assertFalse(result["success"])
		self.assertFalse(result["retryable"])


class TestProviderRegistration(FrappeTestCase):
	"""The core registry must see the rabbitmq provider via the hook."""

	def test_provider_registered(self) -> None:
		from frappe_event_bus.providers.registry import clear_cache, get_providers

		clear_cache()
		frappe.local._event_bus_provider_cache = None
		providers = get_providers()
		self.assertIn("rabbitmq", providers)
		self.assertEqual(
			providers["rabbitmq"]["connection_doctype"],
			"RabbitMQ Event Bus Connection",
		)
		self.assertEqual(
			providers["rabbitmq"]["publisher"],
			"frappe_event_bus_rabbitmq.publisher.RabbitMQPublisher",
		)
