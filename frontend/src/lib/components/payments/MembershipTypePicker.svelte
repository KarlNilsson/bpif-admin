<script lang="ts">
	import * as RadioGroup from '#lib/components/ui/radio-group/index.js';
	import type { MembershipType } from '#lib/types/membershipTypes.ts';
	import { formatCurrency } from '#lib/utils/format.ts';

	let {
		membershipTypes,
		value = $bindable(''),
	}: { membershipTypes: MembershipType[]; value?: string;} = $props();
</script>

<RadioGroup.Root bind:value aria-label="Medlemskap">
	{#each membershipTypes as membershipType (membershipType.id)}
		{@const id = `membership-type-${membershipType.id}`}
		<label
			for={id}
			class="flex cursor-pointer items-center gap-3 rounded-lg border bg-background p-3 has-data-[state=checked]:border-primary"
		>
			<RadioGroup.Item {id} value={String(membershipType.id)} />
			<span class="font-medium">{membershipType.name}</span>
			<span class="ml-auto text-muted-foreground">{formatCurrency(membershipType.amount_ore)}</span>
		</label>
	{/each}
</RadioGroup.Root>
