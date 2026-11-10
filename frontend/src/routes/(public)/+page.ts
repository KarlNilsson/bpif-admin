import { listMembershipTypes } from '#lib/api/membershipTypes.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	return { membershipTypes: await listMembershipTypes(fetch) };
};
