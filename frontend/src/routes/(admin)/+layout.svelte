<script lang="ts">
	import AdminNav from '#lib/components/layout/AdminNav.svelte';
	import SiteHeader from '#lib/components/layout/SiteHeader.svelte';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();
</script>

<div class="min-h-dvh bg-muted/40">
	<SiteHeader title="BPIF – administration">
		<AdminNav />
	</SiteHeader>
	<main class="mx-auto w-full max-w-5xl px-4 py-8">
		{@render children()}
	</main>
</div>
