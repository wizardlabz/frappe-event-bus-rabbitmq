"""RabbitMQ publisher implementing the Frappe Event Bus provider contract.

The module exposes :class:`RabbitMQPublisher` (an :class:`EventBusProvider`
subclass) plus :func:`classify_failure`, a *pure* function that maps a ``pika``
exception to ``(error_message, retryable)``. Keeping classification pure makes
it unit-testable without a live broker.
"""

from __future__ import annotations

import socket
import ssl
from typing import Any

import frappe
import pika
import pika.exceptions as pe
from frappe_event_bus.providers.interface import (
	EventBusProvider,
	publish_failure,
	publish_success,
)

CONNECTION_DOCTYPE = "RabbitMQ Event Bus Connection"
DESTINATION_DOCTYPE = "RabbitMQ Event Bus Destination"


def classify_failure(exc: BaseException) -> tuple[str, bool]:
	"""Map an exception raised while publishing to ``(message, retryable)``.

	Retryable (transient) failures:
	  * :class:`pika.exceptions.AMQPConnectionError` and subclasses
	  * socket timeouts / connection resets
	  * :class:`pika.exceptions.ConnectionClosed`

	Non-retryable (permanent / config) failures:
	  * authentication errors
	  * channel errors raised by the broker (e.g. missing exchange, 404,
	    precondition failures)
	  * publisher-confirm negative acks / unroutable messages

	Unknown exceptions default to retryable and are logged via
	:func:`frappe.log_error` so they can be investigated.

	Args:
		exc: The exception that was raised.

	Returns:
		A tuple of a human-readable message and whether a retry should be
		scheduled.
	"""
	message = str(exc) or exc.__class__.__name__

	# Authentication: bad credentials never succeed on retry. Check before the
	# broader AMQPConnectionError because ProbableAuthenticationError subclasses
	# it.
	if isinstance(exc, pe.ProbableAuthenticationError | pe.AuthenticationError):
		return (f"Authentication failed: {message}", False)

	# Broker-side channel errors: missing exchange, precondition failed, 404 ...
	if isinstance(exc, pe.ChannelClosedByBroker | pe.AMQPChannelError):
		return (f"Broker rejected the channel: {message}", False)

	# Publisher confirms rejected the message, or it was unroutable.
	if isinstance(exc, pe.NackError | pe.UnroutableError):
		return (f"Message was not confirmed by the broker: {message}", False)

	# Transient connectivity problems: retry later.
	if isinstance(
		exc,
		pe.AMQPConnectionError | pe.ConnectionClosed | socket.timeout | socket.gaierror | OSError,
	):
		return (f"Connection error: {message}", True)

	# Unknown: log and let the worker retry.
	frappe.log_error(
		title="RabbitMQ publish: unclassified error",
		message=f"{exc.__class__.__name__}: {message}",
	)
	return (f"Unexpected error: {message}", True)


class RabbitMQPublisher(EventBusProvider):
	"""Publishes Event Bus messages to a RabbitMQ broker via ``pika``."""

	def validate_connection(self, connection_doc: Any) -> None:
		"""Open and immediately close a connection to verify settings.

		Raises:
			frappe.ValidationError: If the broker cannot be reached or the
				credentials are rejected.
		"""
		connection: pika.BlockingConnection | None = None
		try:
			connection = self._connect(connection_doc)
		except (pe.AMQPError, OSError) as exc:
			_msg, _retryable = classify_failure(exc)
			frappe.throw(frappe._("RabbitMQ connection failed: {0}").format(_msg))
		finally:
			_safe_close(connection)

	def validate_destination(self, destination_doc: Any) -> None:
		"""Validate destination configuration without contacting the broker.

		Rules:
		  * ``exchange`` is required.
		  * ``declare_queue`` / ``bind_queue`` require a ``queue_name``.

		Raises:
			frappe.ValidationError: When a rule is violated.
		"""
		if not getattr(destination_doc, "exchange", None):
			frappe.throw(frappe._("Exchange is required."))

		needs_queue = getattr(destination_doc, "bind_queue", 0) or getattr(
			destination_doc, "declare_queue", 0
		)
		if needs_queue and not getattr(destination_doc, "queue_name", None):
			frappe.throw(
				frappe._("Queue Name is required when declaring or binding a queue.")
			)

	def publish(self, message: dict[str, Any]) -> dict[str, Any]:
		"""Publish a normalized message dict and return a normalized result.

		Loads its own connection and destination documents from the docnames
		carried in ``message``.
		"""
		connection_doc = frappe.get_doc(CONNECTION_DOCTYPE, message["connection"])
		destination_doc = frappe.get_doc(DESTINATION_DOCTYPE, message["destination"])

		routing_key = message.get("routing_key") or destination_doc.routing_key or ""
		body = message["payload_json"]
		headers = message.get("headers") or None

		return self._publish_body(connection_doc, destination_doc, routing_key, body, headers)

	def test_publish(
		self,
		connection_doc: Any,
		destination_doc: Any,
		payload: dict[str, Any],
		headers: dict[str, Any] | None = None,
	) -> dict[str, Any]:
		"""Publish a one-off test payload and return a normalized result."""
		routing_key = destination_doc.routing_key or ""
		body = frappe.as_json(payload)
		return self._publish_body(connection_doc, destination_doc, routing_key, body, headers)

	# --- internals -----------------------------------------------------------

	def _publish_body(
		self,
		connection_doc: Any,
		destination_doc: Any,
		routing_key: str,
		body: str,
		headers: dict[str, Any] | None,
	) -> dict[str, Any]:
		"""Connect, optionally declare topology, publish, and close.

		Returns a normalized success/failure dict; never raises for broker
		problems (they are classified into the result instead).
		"""
		connection: pika.BlockingConnection | None = None
		try:
			connection = self._connect(connection_doc)
			channel = connection.channel()
			self._declare_topology(channel, destination_doc, routing_key)

			if destination_doc.publisher_confirms:
				channel.confirm_delivery()

			delivery_mode = 2 if destination_doc.persistent_message else 1
			properties = pika.BasicProperties(
				delivery_mode=delivery_mode,
				headers=headers or None,
				content_type="application/json",
			)
			channel.basic_publish(
				exchange=destination_doc.exchange or "",
				routing_key=routing_key,
				body=body.encode("utf-8") if isinstance(body, str) else body,
				properties=properties,
			)
			return publish_success(
				provider_message_id=None,
				response={
					"exchange": destination_doc.exchange,
					"routing_key": routing_key,
					"confirmed": bool(destination_doc.publisher_confirms),
				},
			)
		except (pe.AMQPError, OSError) as exc:
			error, retryable = classify_failure(exc)
			return publish_failure(error, retryable=retryable)
		except Exception as exc:
			error, retryable = classify_failure(exc)
			return publish_failure(error, retryable=retryable)
		finally:
			_safe_close(connection)

	def _declare_topology(
		self, channel: Any, destination_doc: Any, routing_key: str
	) -> None:
		"""Declare exchange/queue and bind them per the destination flags."""
		if destination_doc.declare_exchange and destination_doc.exchange:
			channel.exchange_declare(
				exchange=destination_doc.exchange,
				exchange_type=destination_doc.exchange_type or "direct",
				durable=bool(destination_doc.durable_exchange),
			)
		if destination_doc.declare_queue and destination_doc.queue_name:
			channel.queue_declare(
				queue=destination_doc.queue_name,
				durable=bool(destination_doc.durable_queue),
			)
		if destination_doc.bind_queue and destination_doc.queue_name:
			channel.queue_bind(
				queue=destination_doc.queue_name,
				exchange=destination_doc.exchange,
				routing_key=routing_key,
			)

	def _connect(self, connection_doc: Any) -> pika.BlockingConnection:
		"""Build connection parameters from ``connection_doc`` and connect."""
		return pika.BlockingConnection(self._build_parameters(connection_doc))

	@staticmethod
	def _build_parameters(connection_doc: Any) -> pika.ConnectionParameters:
		"""Translate a connection document into ``pika.ConnectionParameters``."""
		credentials = pika.PlainCredentials(
			connection_doc.username or "guest",
			connection_doc.get_password("password") if connection_doc.password else "guest",
		)
		ssl_options = None
		if connection_doc.tls_enabled:
			context = ssl.create_default_context()
			if not connection_doc.tls_verify:
				context.check_hostname = False
				context.verify_mode = ssl.CERT_NONE
			ssl_options = pika.SSLOptions(context, server_hostname=connection_doc.host)

		return pika.ConnectionParameters(
			host=connection_doc.host or "localhost",
			port=int(connection_doc.port or 5672),
			virtual_host=connection_doc.virtual_host or "/",
			credentials=credentials,
			socket_timeout=int(connection_doc.connection_timeout or 30),
			heartbeat=int(connection_doc.heartbeat or 60),
			ssl_options=ssl_options,
		)


def _safe_close(connection: pika.BlockingConnection | None) -> None:
	"""Close a connection, ignoring errors raised during teardown."""
	if connection is None or connection.is_closed:
		return
	try:
		connection.close()
	except (pe.AMQPError, OSError):
		pass
