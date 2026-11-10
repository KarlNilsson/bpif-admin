<script lang="ts" module>
	/** Mirrors the backend's MAX_NAMES, which is what actually enforces it. */
	export const MAX_NAMES = 10;

	export interface NameRow {
		id: number;
		value: string;
	}
</script>

<script lang="ts">
	import XIcon from '@lucide/svelte/icons/x';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';

	let {
		rows = $bindable(),
		errors,
		multipleNamesAllowed,
	}: {
		rows: NameRow[];
		/** Error messages by row id. */
		errors: Record<number, string>;
		multipleNamesAllowed: boolean;
	} = $props();

	let nextId = 1;

	function addRow(): void {
		// Row ids only need to be unique among the rows, and the parent starts at 0.
		rows.push({ id: nextId++, value: '' });
	}

	function removeRow(id: number): void {
		rows = rows.filter((row) => row.id !== id);
	}
</script>

<div class="grid gap-2">
	{#each rows as row, index (row.id)}
		<div class="grid gap-1">
			<div class="flex items-center gap-2">
				<Input
					bind:value={row.value}
					placeholder="För- och efternamn"
					autocomplete="off"
					aria-label={`Namn ${index + 1}`}
					aria-invalid={errors[row.id] ? true : undefined}
				/>
				{#if rows.length > 1}
					<Button
						type="button"
						variant="ghost"
						size="icon"
						aria-label={`Ta bort namn ${index + 1}`}
						onclick={() => removeRow(row.id)}
					>
						<XIcon />
					</Button>
				{/if}
			</div>
			{#if errors[row.id]}
				<p class="text-sm text-destructive">{errors[row.id]}</p>
			{/if}
		</div>
	{/each}
	<p class="text-sm text-muted-foreground">Ange alla som avgiften gäller, t.ex. hela familjen.</p>
	{#if multipleNamesAllowed}
	<div>
		<Button type="button" variant="outline" disabled={rows.length >= MAX_NAMES} onclick={addRow}>
			Lägg till namn
		</Button>
	</div>
	{/if}
</div>
