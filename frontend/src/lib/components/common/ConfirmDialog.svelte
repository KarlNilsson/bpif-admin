<script lang="ts">
	import * as AlertDialog from '#lib/components/ui/alert-dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';

	let {
		open = $bindable(false),
		title,
		description,
		confirmLabel,
		destructive = false,
		onconfirm
	}: {
		open?: boolean;
		title: string;
		description: string;
		confirmLabel: string;
		destructive?: boolean;
		/** Handles its own errors. The dialog closes when it settles. */
		onconfirm: () => Promise<void>;
	} = $props();

	let pending = $state(false);

	async function confirm(): Promise<void> {
		pending = true;
		try {
			await onconfirm();
		} finally {
			pending = false;
			open = false;
		}
	}
</script>

<AlertDialog.Root bind:open>
	<AlertDialog.Content>
		<AlertDialog.Header>
			<AlertDialog.Title>{title}</AlertDialog.Title>
			<AlertDialog.Description>{description}</AlertDialog.Description>
		</AlertDialog.Header>
		<AlertDialog.Footer>
			<AlertDialog.Cancel disabled={pending}>Avbryt</AlertDialog.Cancel>
			<!-- Not AlertDialog.Action, which closes before `onconfirm` has finished. -->
			<Button
				variant={destructive ? 'destructive' : 'default'}
				disabled={pending}
				onclick={confirm}
			>
				{confirmLabel}
			</Button>
		</AlertDialog.Footer>
	</AlertDialog.Content>
</AlertDialog.Root>
