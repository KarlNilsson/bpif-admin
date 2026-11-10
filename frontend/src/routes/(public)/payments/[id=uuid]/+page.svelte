<script lang="ts">
	import PaymentQr from '#lib/components/payments/PaymentQr.svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head>
	<title>Betala med Swish – BPIF</title>
</svelte:head>

<Card.Root>
	<Card.Header>
		<Card.Title>Betala med Swish</Card.Title>
	</Card.Header>
	<Card.Content>
		<PaymentQr payment={data.payment} />
	</Card.Content>
</Card.Root>
