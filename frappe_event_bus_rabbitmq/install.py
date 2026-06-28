"""Install-time guards for the RabbitMQ provider app."""

from __future__ import annotations

import frappe


def before_install() -> None:
	"""Refuse to install unless the core ``frappe_event_bus`` app is present."""
	if "frappe_event_bus" not in frappe.get_installed_apps():
		frappe.throw(
			frappe._(
				"Frappe Event Bus RabbitMQ requires the 'frappe_event_bus' app. "
				"Install it first."
			)
		)
