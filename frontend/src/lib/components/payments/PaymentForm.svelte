<script lang="ts">
	import { ApiError, errorMessage, fieldErrors } from '#lib/api/client.ts';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import type { MembershipType } from '#lib/types/membershipTypes.ts';
	import type { PaymentRequestCreate } from '#lib/types/payments.ts';
	import MembershipTypePicker from './MembershipTypePicker.svelte';
	import NameListInput, { type NameRow } from './NameListInput.svelte';

	let {
		membershipTypes,
		onsubmit
	}: {
		membershipTypes: MembershipType[];
		onsubmit: (data: PaymentRequestCreate) => Promise<void>;
	} = $props();

	let membershipTypeId = $state('');
	// Negative, so it can't collide with the ids NameListInput gives new rows.
	let rows = $state<NameRow[]>([{ id: -1, value: '' }]);
	let pending = $state(false);

	let typeError = $state<string | null>(null);
	let namesError = $state<string | null>(null);
	let rowErrors = $state<Record<number, string>>({});
	let formError = $state<string | null>(null);

	let multipleNamesAllowed = $derived((() => {
		const familyMembership = membershipTypes.find((mem) => mem.name.toLocaleLowerCase().localeCompare('familj') === 0);
		return familyMembership?.id.toString() == membershipTypeId;
	})());

	function selectMembershipType(id: string): void {
		membershipTypeId = id;
		if (!multipleNamesAllowed) {
			rows = rows.slice(0, 1);
		}
	}

	function showError(e: unknown, sentRows: NameRow[]): void {
		const errors = fieldErrors(e);
		const keys = Object.keys(errors);

		if (e instanceof ApiError && e.status === 404) {
			formError = 'Medlemskapet finns inte längre. Ladda om sidan.';
		} else if (keys.length === 0) {
			formError = errorMessage(e);
		}
		if (errors['membership_type_id']) {
			typeError = 'Välj ett medlemskap';
		}
		if (errors['names']) {
			namesError = 'Ange mellan 1 och 10 namn';
		}
		sentRows.forEach((row, index) => {
			if (errors[`names.${index}`]) {
				rowErrors[row.id] = 'Namnet måste innehålla bokstäver och vara högst 60 tecken';
			}
		});
	}

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		typeError = null;
		namesError = null;
		rowErrors = {};
		formError = null;

		if (!membershipTypeId) {
			typeError = 'Välj ett medlemskap';
			return;
		}

		// Form housekeeping, not sanitising: that all happens on the server. The
		// sent rows keep their order, so errors can be mapped back to them.
		const sentRows = rows.filter((row) => row.value.trim() !== '');

		pending = true;
		try {
			await onsubmit({
				names: sentRows.map((row) => row.value),
				membership_type_id: Number(membershipTypeId)
			});
		} catch (e) {
			showError(e, sentRows);
		} finally {
			pending = false;
		}
	}
</script>

<form class="grid gap-6" onsubmit={submit} novalidate>
	<fieldset class="grid gap-2">
		<Label>Medlemskap</Label>
		<MembershipTypePicker {membershipTypes} bind:value={() => membershipTypeId, selectMembershipType} />
		{#if typeError}
			<p class="text-sm text-destructive">{typeError}</p>
		{/if}
	</fieldset>

	<fieldset class="grid gap-2">
		<Label>Namn</Label>
		<NameListInput bind:rows errors={rowErrors} {multipleNamesAllowed} />
		{#if namesError}
			<p class="text-sm text-destructive">{namesError}</p>
		{/if}
	</fieldset>

	{#if formError}
		<p class="text-sm text-destructive">{formError}</p>
	{/if}

	<Button type="submit" disabled={pending}>
		{pending ? 'Skapar QR-kod…' : 'Skapa QR-kod'}
	</Button>
</form>
