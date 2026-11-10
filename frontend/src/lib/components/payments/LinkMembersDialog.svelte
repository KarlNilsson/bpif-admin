<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { errorMessage } from '#lib/api/client.ts';
	import { listMembers } from '#lib/api/members.ts';
	import ConfirmDialog from '#lib/components/common/ConfirmDialog.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import type { Member } from '#lib/types/members.ts';
	import type { PaymentRequestAdmin } from '#lib/types/payments.ts';
	import { debounce } from '#lib/utils/debounce.ts';
	import { formatCurrency } from '#lib/utils/format.ts';

	let {
		payment,
		onclose,
		onconfirm
	}: {
		payment: PaymentRequestAdmin;
		onclose: () => void;
		/** Handles its own errors. */
		onconfirm: (memberIds: number[]) => Promise<void>;
	} = $props();

	interface NameSearch {
		query: string;
		results: Member[];
	}

	// Pre-filled with the submitted names. Name matching is never automatic: the
	// administrator chooses every member.
	let searches = $state<NameSearch[]>(
		untrack(() => payment.names.map((name) => ({ query: name, results: [] })))
	);
	let selected = $state<Member[]>([]);
	let confirmOpen = $state(false);

	let linkedIds = $derived(payment.fees.map((fee) => fee.member.id));
	let selectedNames = $derived(selected.map((member) => member.name).join(', '));

	async function runSearch(search: NameSearch): Promise<void> {
		const query = search.query;
		try {
			const results = await listMembers(fetch, { search: query.trim() });
			// A slower, older response must not replace a newer one.
			if (search.query === query) {
				search.results = results;
			}
		} catch (e) {
			toast.error(errorMessage(e));
		}
	}

	const debouncedSearches = untrack(() => searches.map((search) => debounce(() => runSearch(search))));

	function isChosen(member: Member): boolean {
		return linkedIds.includes(member.id) || selected.some((other) => other.id === member.id);
	}

	onMount(() => {
		searches.forEach((search) => runSearch(search));
	});
</script>

<Dialog.Root open onOpenChange={(open) => !open && onclose()}>
	<Dialog.Content class="max-h-[85dvh] overflow-y-auto sm:max-w-xl">
		<Dialog.Header>
			<Dialog.Title>Markera avgifter som betalda</Dialog.Title>
			<Dialog.Description>
				{payment.message}, {formatCurrency(payment.amount_ore)}. Sök fram de medlemmar betalningen
				gäller.
			</Dialog.Description>
		</Dialog.Header>

		<div class="grid gap-4">
			{#each searches as search, index (index)}
				<div class="grid gap-2">
					<Input
						aria-label={`Sök medlem för ${payment.names[index]}`}
						bind:value={search.query}
						oninput={debouncedSearches[index]}
					/>
					<ul class="grid gap-1">
						{#each search.results as member (member.id)}
							<li class="flex items-center justify-between gap-2 text-sm">
								<span>
									{member.name} ({member.member_number}), {member.membership_type.name}
								</span>
								<Button
									variant="outline"
									size="sm"
									disabled={isChosen(member)}
									onclick={() => selected.push(member)}
								>
									Lägg till
								</Button>
							</li>
						{:else}
							<li class="text-sm text-muted-foreground">Inga medlemmar hittades</li>
						{/each}
					</ul>
				</div>
			{/each}

			{#if selected.length > 0}
				<div class="grid gap-1">
					<p class="text-sm font-medium">Valda medlemmar</p>
					<ul class="grid gap-1">
						{#each selected as member (member.id)}
							<li class="flex items-center justify-between gap-2 text-sm">
								<span>{member.name} ({member.member_number})</span>
								<Button
									variant="ghost"
									size="sm"
									onclick={() => (selected = selected.filter((other) => other.id !== member.id))}
								>
									Ta bort
								</Button>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		</div>

		<Dialog.Footer>
			<Button disabled={selected.length === 0} onclick={() => (confirmOpen = true)}>
				Markera som betalda
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<ConfirmDialog
	bind:open={confirmOpen}
	title="Markera avgifter som betalda?"
	description={`Markerar avgifterna för ${payment.year} som betalda för: ${selectedNames}. Saknade avgifter skapas med medlemmens nuvarande medlemstyp. Kontrollera att betalningen på ${formatCurrency(payment.amount_ore)} syns i Swish innan du bekräftar.`}
	confirmLabel="Markera som betalda"
	onconfirm={() => onconfirm(selected.map((member) => member.id))}
/>
