import { getHealth } from '#lib/api/health.ts';
import type { Health } from '#lib/types/health.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	let health: Health | null = null;
	try {
		health = await getHealth(fetch);
	} catch {
		// The page reports the API as unavailable instead of failing.
	}
	return { health };
};
