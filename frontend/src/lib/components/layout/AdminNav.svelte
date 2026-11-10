<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { Button } from '#lib/components/ui/button/index.js';

	const items = [
		{ href: resolve('/(admin)/payments'), label: 'Betalningar' },
		{ href: resolve('/(admin)/status'), label: 'Status' }
	];
</script>

{#each items as item (item.href)}
	{@const active = page.url.pathname === item.href}
	<Button
		href={item.href}
		variant={active ? 'secondary' : 'ghost'}
		aria-current={active ? 'page' : undefined}
	>
		{item.label}
	</Button>
{/each}
