<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { createPaymentRequest } from '#lib/api/payments.ts';
	import PaymentForm from '#lib/components/payments/PaymentForm.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import type { PaymentRequestCreate } from '#lib/types/payments.ts';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	async function submit(request: PaymentRequestCreate): Promise<void> {
		const payment = await createPaymentRequest(fetch, request);
		await goto(resolve('/(public)/payments/[id=uuid]', { id: payment.id }));
	}
</script>

<svelte:head>
	<title>Betala medlemsavgift – BPIF</title>
</svelte:head>

<Card.Root>
	<Card.Header>
		<Card.Title>Betala medlemsavgift</Card.Title>
		<Card.Description>
			Välj medlemskap och fyll i namnen på dem som avgiften gäller. Du får en QR-kod att skanna med
			Swish.
		</Card.Description>
	</Card.Header>
	<Card.Content>
		<PaymentForm membershipTypes={data.membershipTypes} onsubmit={submit} />
	</Card.Content>
</Card.Root>
