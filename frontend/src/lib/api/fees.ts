import type { Fee } from '#lib/types/fees.ts';
import { api, type Fetch } from './client.ts';

export function markFeeUnpaid(fetchFn: Fetch, id: number): Promise<Fee> {
	return api.post<Fee>(fetchFn, `/fees/${id}/mark-unpaid`);
}
