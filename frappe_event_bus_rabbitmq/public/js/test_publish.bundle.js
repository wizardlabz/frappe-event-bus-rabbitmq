/**
 * Vue 3 "Test Publish" panel for RabbitMQ Event Bus Destinations.
 *
 * Adds a "Test Publish" button to the Destination form. Clicking it opens a
 * dialog hosting a small reactive Vue app that calls the whitelisted
 * `test_publish` API and renders the normalized provider result (success badge,
 * error message and the raw provider response).
 */

import { createApp, defineComponent, reactive } from "vue";

const TEST_PUBLISH_METHOD =
	"frappe_event_bus_rabbitmq.doctype.rabbitmq_event_bus_destination.rabbitmq_event_bus_destination.test_publish";

const TestPublishPanel = defineComponent({
	name: "TestPublishPanel",
	props: {
		destination: { type: String, required: true },
	},
	setup(props) {
		const state = reactive({
			loading: false,
			success: null,
			error: "",
			response: "",
			payload: '{\n  "_test": true\n}',
		});

		async function runTestPublish() {
			state.loading = true;
			state.error = "";
			state.response = "";
			state.success = null;
			try {
				const r = await frappe.call({
					method: TEST_PUBLISH_METHOD,
					args: { destination_name: props.destination, payload: state.payload },
				});
				const data = r.message || {};
				state.success = !!data.success;
				if (data.success) {
					state.response = JSON.stringify(data.response || {}, null, 2);
				} else {
					state.error = data.error || __("Unknown error");
				}
			} catch (e) {
				state.success = false;
				state.error = (e && e.message) || String(e);
			} finally {
				state.loading = false;
			}
		}

		return { state, runTestPublish, __ };
	},
	template: `
		<div class="rmq-test-publish">
			<label class="control-label">{{ __('Sample Payload (JSON)') }}</label>
			<textarea class="form-control mb-2" rows="4" v-model="state.payload"></textarea>
			<button class="btn btn-primary btn-sm mb-3" :disabled="state.loading" @click="runTestPublish">
				{{ state.loading ? __('Publishing...') : __('Publish Test Message') }}
			</button>
			<div v-if="state.success === true" class="indicator-pill green mb-2">{{ __('Published') }}</div>
			<div v-if="state.success === false" class="indicator-pill red mb-2">{{ __('Failed') }}</div>
			<pre v-if="state.response" class="rmq-output">{{ state.response }}</pre>
			<div v-if="state.error" class="text-danger">{{ state.error }}</div>
		</div>
	`,
});

function openTestPublishDialog(frm) {
	if (frm.is_dirty() || frm.is_new()) {
		frappe.msgprint(__("Please save the destination first."));
		return;
	}
	const dialog = new frappe.ui.Dialog({
		title: __("Test Publish"),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "panel_area" }],
	});
	dialog.show();

	const mountPoint = dialog.fields_dict.panel_area.$wrapper.get(0);
	const app = createApp(TestPublishPanel, { destination: frm.doc.name });
	app.mount(mountPoint);
	dialog.onhide = () => app.unmount();
}

frappe.ui.form.on("RabbitMQ Event Bus Destination", {
	refresh(frm) {
		frm.add_custom_button(__("Test Publish"), () => openTestPublishDialog(frm));
	},
});
