<script lang="ts">
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import type { LinkedFee, PaymentRequestAdmin } from '#lib/types/payments.ts';
	import { formatCurrency, formatDate, formatDateTime } from '#lib/utils/format.ts';

	let {
		payments,
		onmatch,
		onundo
	}: {
		payments: PaymentRequestAdmin[];
		onmatch: (payment: PaymentRequestAdmin) => void;
		onundo: (fee: LinkedFee) => void;
	} = $props();
</script>

<Table.Root>
	<Table.Header>
		<Table.Row>
			<Table.Head>Skapad</Table.Head>
			<Table.Head>Meddelande</Table.Head>
			<Table.Head>Belopp</Table.Head>
			<Table.Head>Kopplade medlemmar</Table.Head>
			<Table.Head><span class="sr-only">Åtgärder</span></Table.Head>
		</Table.Row>
	</Table.Header>
	<Table.Body>
		{#each payments as payment (payment.id)}
			<Table.Row>
				<Table.Cell>{formatDateTime(payment.created_at)}</Table.Cell>
				<Table.Cell class="whitespace-normal">{payment.message}</Table.Cell>
				<Table.Cell>{formatCurrency(payment.amount_ore)}</Table.Cell>
				<Table.Cell>
					<ul class="grid gap-1">
						{#each payment.fees as fee (fee.id)}
							<li class="flex flex-wrap items-center gap-2">
								<span>{fee.member.name} ({fee.member.member_number})</span>
								<Badge variant="secondary">Betald {formatDate(fee.paid_at)}</Badge>
								<Button variant="ghost" size="sm" onclick={() => onundo(fee)}>Ångra</Button>
							</li>
						{:else}
							<li class="text-muted-foreground">Ingen</li>
						{/each}
					</ul>
				</Table.Cell>
				<Table.Cell class="text-right">
					<Button variant="outline" size="sm" onclick={() => onmatch(payment)}>
						Markera avgifter som betalda
					</Button>
				</Table.Cell>
			</Table.Row>
		{/each}
	</Table.Body>
</Table.Root>
