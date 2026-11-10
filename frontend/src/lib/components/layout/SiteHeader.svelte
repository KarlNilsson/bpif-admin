<script lang="ts">
	import type { Snippet } from 'svelte';
	import { resolve } from '$app/paths';

	let { title, children }: { title: string; children?: Snippet } = $props();
</script>

<header class="border-b bg-background">
	<div class="mx-auto flex h-14 max-w-5xl items-center justify-between gap-4 px-4">
		<a href={resolve('/(public)')} class="text-lg font-semibold tracking-tight">{title}</a>
		{#if children}
			<nav class="flex items-center gap-2">
				{@render children()}
			</nav>
		{/if}
	</div>
</header>
