<script lang="ts">
	import '../app.css';
	import favicon from '#lib/assets/favicon.svg';
	import { Toaster } from '#lib/components/ui/sonner/index.js';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>BPIF</title>
</svelte:head>

{@render children()}

<!-- Light like the rest of the app (no dark mode yet), even when the OS is dark. -->
<Toaster richColors theme="light" />
