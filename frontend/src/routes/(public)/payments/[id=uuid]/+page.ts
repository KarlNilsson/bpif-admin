import { orNotFound } from '#lib/api/client.ts';
import { getPaymentRequest } from '#lib/api/payments.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	return {
		payment: await orNotFound(getPaymentRequest(fetch, params.id), 'Betalningen hittades inte')
	};
};
