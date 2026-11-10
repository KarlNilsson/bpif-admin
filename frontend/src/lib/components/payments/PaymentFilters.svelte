<script lang="ts" module>
	export interface PaymentFilterValues {
		year: number;
		search: string;
		unlinkedOnly: boolean;
	}
</script>

<script lang="ts">
	import { untrack } from 'svelte';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import * as Select from '#lib/components/ui/select/index.js';
	import { debounce } from '#lib/utils/debounce.ts';

	let {
		filters,
		onchange
	}: {
		filters: PaymentFilterValues;
		onchange: (changes: Partial<PaymentFilterValues>) => void;
	} = $props();

	// Around the shown year, which comes from the backend. The browser's clock is
	// never used.
	let years = $derived(Array.from({ length: 5 }, (_, i) => filters.year + 1 - i));

	// Only the user changes it. Following `filters` would overwrite what they type
	// while a search is loading.
	let search = $state(untrack(() => filters.search));

	const searchChanged = debounce((value: string) => onchange({ search: value }));
</script>

<div class="flex flex-wrap items-end gap-4">
	<div class="grid gap-2">
		<Label>År</Label>
		<Select.Root
			type="single"
			value={String(filters.year)}
			onValueChange={(value) => onchange({ year: Number(value) })}
		>
			<Select.Trigger class="w-28" aria-label="År">{filters.year}</Select.Trigger>
			<Select.Content>
				{#each years as year (year)}
					<Select.Item value={String(year)} label={String(year)}>{year}</Select.Item>
				{/each}
			</Select.Content>
		</Select.Root>
	</div>
	<div class="grid gap-2">
		<Label for="payment-search">Sök på namn</Label>
		<Input
			id="payment-search"
			class="w-64"
			bind:value={search}
			oninput={() => searchChanged(search)}
		/>
	</div>
	<div class="flex h-9 items-center gap-2">
		<Checkbox
			id="payment-unlinked"
			checked={filters.unlinkedOnly}
			onCheckedChange={(checked) => onchange({ unlinkedOnly: checked })}
		/>
		<Label for="payment-unlinked">Visa bara ej kopplade</Label>
	</div>
</div>
