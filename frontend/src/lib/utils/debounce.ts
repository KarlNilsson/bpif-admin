/** Delays calls to `fn` until `ms` milliseconds have passed without a new call. */
export function debounce<Args extends unknown[]>(
	fn: (...args: Args) => void,
	ms = 300
): (...args: Args) => void {
	let timer: ReturnType<typeof setTimeout> | undefined;
	return (...args) => {
		clearTimeout(timer);
		timer = setTimeout(() => fn(...args), ms);
	};
}
