import type { MembershipType } from '#lib/types/membershipTypes.ts';
import { api, type Fetch } from './client.ts';

export function listMembershipTypes(fetchFn: Fetch): Promise<MembershipType[]> {
	return api.get<MembershipType[]>(fetchFn, '/membership-types');
}
