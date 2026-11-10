<script lang="ts">
	import { resolve } from '$app/paths';
	import { qrImageUrl } from '#lib/api/payments.ts';
	import { Button } from '#lib/components/ui/button/index.js';
	import type { PaymentRequest } from '#lib/types/payments.ts';
	import { formatCurrency, formatSwishNumber } from '#lib/utils/format.ts';

	let { payment }: { payment: PaymentRequest } = $props();

	let details = $derived([
		{ label: 'Belopp', value: formatCurrency(payment.amount_ore) },
		{ label: 'Mottagare', value: formatSwishNumber(payment.swish_number) },
		{ label: 'Meddelande', value: payment.message },
		{ label: 'Namn', value: payment.names.join(', ') }
	]);
</script>

<div class="grid gap-6">
	<!-- A fixed size, so the layout doesn't jump while the image loads. -->
	<img
		src={qrImageUrl(payment.id)}
		alt="QR-kod för Swish-betalning"
		width="288"
		height="288"
		class="mx-auto size-72 rounded-lg border bg-white"
	/>

	<div class="grid gap-2 text-center">
		<div>
			<Button href={payment.payment_url}>Öppna Swish</Button>
		</div>
		<p class="text-sm text-muted-foreground">
			På mobilen: tryck på knappen. På datorn: skanna QR-koden med mobilens kamera.
		</p>
	</div>

	<dl class="divide-y">
		{#each details as detail (detail.label)}
			<div class="flex justify-between gap-4 py-2">
				<dt class="font-medium">{detail.label}</dt>
				<dd class="text-right">{detail.value}</dd>
			</div>
		{/each}
	</dl>

	<div class="grid gap-2 text-sm text-muted-foreground">
		<p>Ändra inte meddelandet i Swish – det används för att koppla betalningen till rätt medlem.</p>
		<p>Avgiften markeras som betald när föreningen har stämt av betalningen.</p>
	</div>

	<div>
		<Button variant="outline" href={resolve('/(public)')}>Gör en ny betalning</Button>
	</div>
</div>
