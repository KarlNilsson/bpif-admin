import type { Health } from '#lib/types/health.ts';
import { request, type Fetch } from './client';

export function getHealth(fetchFn: Fetch): Promise<Health> {
	return request<Health>(fetchFn, '/health');
}
