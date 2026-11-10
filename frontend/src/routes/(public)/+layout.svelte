<script lang="ts">
	import SiteHeader from '#lib/components/layout/SiteHeader.svelte';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();
</script>

<div class="min-h-dvh bg-muted/40">
	<SiteHeader title="BPIF" />
	<main class="mx-auto w-full max-w-xl px-4 py-8">
		{@render children()}
	</main>
</div>
