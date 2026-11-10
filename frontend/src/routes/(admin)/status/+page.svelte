<script lang="ts">
	import { Badge } from '#lib/components/ui/badge/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let rows = $derived([
		{ label: 'API', ok: data.health !== null },
		{ label: 'Databas', ok: data.health?.database === 'ok' }
	]);
</script>

<svelte:head>
	<title>Status – BPIF</title>
</svelte:head>

<Card.Root class="max-w-xl">
	<Card.Header>
		<Card.Title>Systemstatus</Card.Title>
		<Card.Description>Status för BPIF:s administrationsverktyg.</Card.Description>
	</Card.Header>
	<Card.Content>
		<dl class="divide-y">
			{#each rows as row (row.label)}
				<div class="flex items-center justify-between py-3 first:pt-0 last:pb-0">
					<dt class="font-medium">{row.label}</dt>
					<dd>
						{#if row.ok}
							<Badge variant="secondary">OK</Badge>
						{:else}
							<Badge variant="destructive">Ej tillgänglig</Badge>
						{/if}
					</dd>
				</div>
			{/each}
		</dl>
	</Card.Content>
</Card.Root>
