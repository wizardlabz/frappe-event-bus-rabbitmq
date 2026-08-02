"""Destination-level headers are merged into the published AMQP headers.

The destination's ``headers_template`` supplies defaults for every message sent
there. Rule-level headers, rendered earlier with full document context, win on
any key collision — the more specific configuration should beat the default.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_event_bus_rabbitmq.publisher import merge_destination_headers


class TestMergeDestinationHeaders(FrappeTestCase):
	def test_blank_template_leaves_headers_untouched(self):
		dest = frappe._dict(headers_template=None)
		self.assertEqual(merge_destination_headers(dest, {"a": 1}), {"a": 1})

	def test_blank_template_with_no_headers_yields_none(self):
		dest = frappe._dict(headers_template="")
		self.assertIsNone(merge_destination_headers(dest, None))

	def test_destination_headers_are_applied(self):
		dest = frappe._dict(headers_template='{"x-source": "erp"}')
		self.assertEqual(merge_destination_headers(dest, None), {"x-source": "erp"})

	def test_message_headers_win_on_collision(self):
		dest = frappe._dict(headers_template='{"x-source": "destination", "x-only": "d"}')
		out = merge_destination_headers(dest, {"x-source": "rule"})
		self.assertEqual(out, {"x-source": "rule", "x-only": "d"})

	def test_template_can_reference_the_message(self):
		dest = frappe._dict(headers_template='{"x-doctype": "{{ message.reference_doctype }}"}')
		out = merge_destination_headers(dest, None, {"reference_doctype": "ToDo"})
		self.assertEqual(out, {"x-doctype": "ToDo"})

	def test_invalid_template_does_not_break_publishing(self):
		dest = frappe._dict(headers_template="{not json at all")
		self.assertEqual(merge_destination_headers(dest, {"a": 1}), {"a": 1})
