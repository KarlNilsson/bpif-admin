import type { Health } from '#lib/types/health.ts';
import { api, type Fetch } from './client.ts';

export function getHealth(fetchFn: Fetch): Promise<Health> {
	return api.get<Health>(fetchFn, '/health');
}
