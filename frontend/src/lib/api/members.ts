import type { Member } from '#lib/types/members.ts';
import { api, type Fetch } from './client.ts';

export function listMembers(fetchFn: Fetch, filters: { search?: string } = {}): Promise<Member[]> {
	return api.get<Member[]>(fetchFn, '/members', filters);
}
