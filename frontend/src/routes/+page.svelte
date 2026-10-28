<script lang="ts">
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<h1>bpif-admin</h1>

<dl>
	<dt>API</dt>
	<dd>{data.health ? 'ok' : 'unavailable'}</dd>
	<dt>Database</dt>
	<dd>{data.health?.database ?? 'unavailable'}</dd>
</dl>
