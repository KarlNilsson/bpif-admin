<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Card from '#lib/components/ui/card/index.js';

	let title = $derived(page.status === 404 ? 'Sidan hittades inte' : 'Något gick fel');
	// SvelteKit's own messages (e.g. 'Not Found') are English and repeat the
	// status; only show messages that add information.
	let message = $derived.by(() => {
		const text = page.error?.message;
		if (!text || text === title || text === 'Not Found' || text === 'Internal Error') {
			return null;
		}
		return text;
	});
</script>

<svelte:head>
	<title>{title} – BPIF</title>
</svelte:head>

<main class="flex min-h-dvh items-center justify-center bg-muted/40 p-4">
	<Card.Root class="w-full max-w-md">
		<Card.Header>
			<Card.Description>Fel {page.status}</Card.Description>
			<Card.Title class="text-2xl">{title}</Card.Title>
		</Card.Header>
		{#if message}
			<Card.Content>
				<p class="text-muted-foreground">{message}</p>
			</Card.Content>
		{/if}
		<Card.Footer>
			<Button href={resolve('/(public)')}>Till startsidan</Button>
		</Card.Footer>
	</Card.Root>
</main>
