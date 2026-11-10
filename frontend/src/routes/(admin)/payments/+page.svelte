<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { goto, invalidate } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { errorMessage } from '#lib/api/client.ts';
	import { markFeeUnpaid } from '#lib/api/fees.ts';
	import { markPaymentFeesPaid } from '#lib/api/payments.ts';
	import ConfirmDialog from '#lib/components/common/ConfirmDialog.svelte';
	import LinkMembersDialog from '#lib/components/payments/LinkMembersDialog.svelte';
	import PaymentFilters, {
		type PaymentFilterValues
	} from '#lib/components/payments/PaymentFilters.svelte';
	import PaymentRequestTable from '#lib/components/payments/PaymentRequestTable.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import type { LinkedFee, PaymentRequestAdmin } from '#lib/types/payments.ts';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let filters: PaymentFilterValues = $derived({
		year: data.list.year,
		search: data.search,
		unlinkedOnly: data.unlinkedOnly
	});

	let matching = $state<PaymentRequestAdmin | null>(null);
	let undoing = $state<LinkedFee | null>(null);
	let undoOpen = $state(false);

	function updateFilters(changes: Partial<PaymentFilterValues>): void {
		const next = { ...filters, ...changes };
		const params = new URLSearchParams({
			year: String(next.year),
			...(next.search && { q: next.search }),
			...(next.unlinkedOnly && { linked: 'false' })
		});
		goto(resolve(`/(admin)/payments?${params}`), { replace: true, reset: false });
	}

	async function markPaid(payment: PaymentRequestAdmin, memberIds: number[]): Promise<void> {
		try {
			const { marked, created, already_paid } = await markPaymentFeesPaid(
				fetch,
				payment.id,
				memberIds
			);
			const fees = marked === 1 ? '1 avgift markerad som betald' : `${marked} avgifter markerade som betalda`;
			toast.success(`${fees} (${created} nya, ${already_paid} var redan betalda)`);
			matching = null;
			await invalidate('app:payments');
		} catch (e) {
			toast.error(errorMessage(e));
		}
	}

	function askToUndo(fee: LinkedFee): void {
		undoing = fee;
		undoOpen = true;
	}

	async function undo(): Promise<void> {
		if (!undoing) {
			return;
		}
		try {
			await markFeeUnpaid(fetch, undoing.id);
			toast.success('Betalningen är ångrad');
		} catch (e) {
			toast.error(errorMessage(e, { 409: 'Avgiften har redan ändrats. Listan har uppdaterats.' }));
		}
		await invalidate('app:payments');
	}
</script>

<svelte:head>
	<title>Betalningar {data.list.year} – BPIF</title>
</svelte:head>

<div class="grid gap-6">
	<h1 class="text-2xl font-semibold tracking-tight">Betalningar {data.list.year}</h1>

	<PaymentFilters {filters} onchange={updateFilters} />

	<Card.Root>
		<Card.Content>
			{#if data.list.items.length > 0}
				<PaymentRequestTable
					payments={data.list.items}
					onmatch={(payment) => (matching = payment)}
					onundo={askToUndo}
				/>
			{:else}
				<p class="text-muted-foreground">Inga betalningar hittades för {data.list.year}.</p>
			{/if}
		</Card.Content>
	</Card.Root>
</div>

{#if matching}
	{@const payment = matching}
	{#key payment.id}
		<LinkMembersDialog
			{payment}
			onclose={() => (matching = null)}
			onconfirm={(memberIds) => markPaid(payment, memberIds)}
		/>
	{/key}
{/if}

<ConfirmDialog
	bind:open={undoOpen}
	title="Ångra betalning?"
	description={`Avgiften för ${undoing?.member.name ?? ''} markeras som obetald igen.`}
	confirmLabel="Ångra"
	onconfirm={undo}
/>
