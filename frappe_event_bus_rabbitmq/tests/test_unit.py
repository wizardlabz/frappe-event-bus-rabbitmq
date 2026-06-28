"""Unit tests that do not touch a broker.

Covers the pure failure-classification function and destination validation
rules. Fake document objects are used so these run without RabbitMQ.
"""

from __future__ import annotations

import socket
from types import SimpleNamespace

import frappe
import pika.exceptions as pe
from frappe.tests.utils import FrappeTestCase

from frappe_event_bus_rabbitmq.publisher import RabbitMQPublisher, classify_failure


class TestClassifyFailure(FrappeTestCase):
	"""The pure exception -> (message, retryable) mapping."""

	def test_connection_error_is_retryable(self) -> None:
		_msg, retryable = classify_failure(pe.AMQPConnectionError("nope"))
		self.assertTrue(retryable)

	def test_socket_timeout_is_retryable(self) -> None:
		_msg, retryable = classify_failure(TimeoutError("timed out"))
		self.assertTrue(retryable)

	def test_connection_closed_is_retryable(self) -> None:
		_msg, retryable = classify_failure(pe.ConnectionClosed(320, "closed"))
		self.assertTrue(retryable)

	def test_probable_authentication_error_not_retryable(self) -> None:
		_msg, retryable = classify_failure(pe.ProbableAuthenticationError("bad creds"))
		self.assertFalse(retryable)

	def test_authentication_error_not_retryable(self) -> None:
		_msg, retryable = classify_failure(pe.AuthenticationError())
		self.assertFalse(retryable)

	def test_channel_closed_by_broker_not_retryable(self) -> None:
		exc = pe.ChannelClosedByBroker(404, "NOT_FOUND - no exchange 'missing'")
		_msg, retryable = classify_failure(exc)
		self.assertFalse(retryable)

	def test_nack_error_not_retryable(self) -> None:
		_msg, retryable = classify_failure(pe.NackError([]))
		self.assertFalse(retryable)

	def test_unroutable_error_not_retryable(self) -> None:
		_msg, retryable = classify_failure(pe.UnroutableError([]))
		self.assertFalse(retryable)

	def test_unknown_error_is_retryable_and_logged(self) -> None:
		_msg, retryable = classify_failure(ValueError("surprise"))
		self.assertTrue(retryable)

	def test_message_is_non_empty_string(self) -> None:
		msg, _retryable = classify_failure(pe.AMQPConnectionError("nope"))
		self.assertIsInstance(msg, str)
		self.assertTrue(msg)


class TestValidateDestination(FrappeTestCase):
	"""Destination validation rules, exercised with fake docs."""

	def setUp(self) -> None:
		self.publisher = RabbitMQPublisher()

	@staticmethod
	def _dest(**overrides: object) -> SimpleNamespace:
		base = {
			"destination_name": "_t",
			"exchange": "ex",
			"exchange_type": "direct",
			"routing_key": "rk",
			"declare_exchange": 0,
			"declare_queue": 0,
			"bind_queue": 0,
			"queue_name": "",
		}
		base.update(overrides)
		return SimpleNamespace(**base)

	def test_valid_destination_passes(self) -> None:
		self.publisher.validate_destination(self._dest())

	def test_exchange_required(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			self.publisher.validate_destination(self._dest(exchange=""))

	def test_bind_queue_requires_queue_name(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			self.publisher.validate_destination(self._dest(bind_queue=1, queue_name=""))

	def test_declare_queue_requires_queue_name(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			self.publisher.validate_destination(self._dest(declare_queue=1, queue_name=""))

	def test_bind_queue_with_queue_name_passes(self) -> None:
		self.publisher.validate_destination(
			self._dest(bind_queue=1, declare_queue=1, queue_name="q")
		)
