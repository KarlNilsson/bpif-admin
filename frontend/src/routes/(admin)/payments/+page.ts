import { listPaymentRequests } from '#lib/api/payments.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:payments');

	const yearParam = url.searchParams.get('year');
	const year = yearParam && /^\d{4}$/.test(yearParam) ? Number(yearParam) : undefined;
	const search = url.searchParams.get('q') ?? '';
	const unlinkedOnly = url.searchParams.get('linked') === 'false';

	const list = await listPaymentRequests(fetch, {
		year,
		search: search || undefined,
		linked: unlinkedOnly ? false : undefined
	});
	return { list, search, unlinkedOnly };
};
