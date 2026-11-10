// The shared HTTP wrapper. This is the only module that calls `fetch`: domain
// modules (`lib/api/<domain>.ts`) wrap `api` in typed functions, and
// components never import this module directly.
import { error } from '@sveltejs/kit';

export type Fetch = typeof fetch;
export type Query = Record<string, string | number | boolean | null | undefined>;

/** One entry of FastAPI's 422 `detail` list. */
export interface ValidationIssue {
	loc: (string | number)[];
	msg: string;
	type: string;
}

/**
 * A failed API call. `status` is 0 when the server couldn't be reached.
 * `detail` is the backend's (English) `detail`; never show it to users, use
 * `errorMessage` / `fieldErrors` instead.
 */
export class ApiError extends Error {
	readonly status: number;
	readonly detail: string | ValidationIssue[] | undefined;

	constructor(status: number, detail: string | ValidationIssue[] | undefined) {
		super(typeof detail === 'string' ? detail : `API request failed with status ${status}`);
		this.name = 'ApiError';
		this.status = status;
		this.detail = detail;
	}
}

// Relative, except in a build served from another origin than the API (GitHub
// Pages), where VITE_API_ORIGIN is set at build time.
export const API_BASE = `${import.meta.env.VITE_API_ORIGIN ?? ''}/api/v1`;

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

interface RequestOptions {
	query?: Query;
	body?: unknown;
}

function buildUrl(path: string, query?: Query): string {
	const params = new URLSearchParams();
	for (const [key, value] of Object.entries(query ?? {})) {
		if (value !== null && value !== undefined) {
			params.append(key, String(value));
		}
	}
	const search = params.toString();
	return `${API_BASE}${path}${search ? `?${search}` : ''}`;
}

async function parseDetail(response: Response): Promise<ApiError['detail']> {
	try {
		const body: unknown = await response.json();
		if (body && typeof body === 'object' && 'detail' in body) {
			return body.detail as ApiError['detail'];
		}
	} catch {
		// Not JSON (e.g. a proxy error page): there is no detail.
	}
	return undefined;
}

async function request<T>(
	fetchFn: Fetch,
	method: Method,
	path: string,
	{ query, body }: RequestOptions = {}
): Promise<T> {
	const headers: Record<string, string> = { Accept: 'application/json' };
	const init: RequestInit = { method, headers };
	if (body !== undefined) {
		headers['Content-Type'] = 'application/json';
		init.body = JSON.stringify(body);
	}

	let response: Response;
	try {
		response = await fetchFn(buildUrl(path, query), init);
	} catch {
		throw new ApiError(0, undefined);
	}

	if (!response.ok) {
		throw new ApiError(response.status, await parseDetail(response));
	}
	if (response.status === 204) {
		return undefined as T;
	}
	const text = await response.text();
	return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
	get: <T>(fetchFn: Fetch, path: string, query?: Query) =>
		request<T>(fetchFn, 'GET', path, { query }),
	post: <T>(fetchFn: Fetch, path: string, body?: unknown) =>
		request<T>(fetchFn, 'POST', path, { body }),
	put: <T>(fetchFn: Fetch, path: string, body?: unknown) =>
		request<T>(fetchFn, 'PUT', path, { body }),
	patch: <T>(fetchFn: Fetch, path: string, body?: unknown) =>
		request<T>(fetchFn, 'PATCH', path, { body }),
	delete: <T = void>(fetchFn: Fetch, path: string) => request<T>(fetchFn, 'DELETE', path)
};

/**
 * Awaits `promise` and turns a 404 from the API into SvelteKit's
 * `error(404)`, so `+error.svelte` handles it. For load functions of `[id]`
 * pages.
 */
export async function orNotFound<T>(
	promise: Promise<T>,
	message = 'Sidan hittades inte'
): Promise<T> {
	try {
		return await promise;
	} catch (e) {
		if (e instanceof ApiError && e.status === 404) {
			error(404, message);
		}
		throw e;
	}
}

const DEFAULT_MESSAGES: Record<number, string> = {
	0: 'Kunde inte nå servern',
	404: 'Hittades inte',
	409: 'Ändringen krockar med befintliga uppgifter',
	422: 'Kontrollera uppgifterna i formuläret'
};

/**
 * A Swedish message for a failed API call, e.g. for a toast. `overrides`
 * gives context-specific messages per status, e.g.
 * `{ 409: 'Medlemsnumret används redan' }`.
 */
export function errorMessage(e: unknown, overrides?: Partial<Record<number, string>>): string {
	// Network failures arrive as ApiError with status 0 (see `request`).
	// Anything that isn't an ApiError is a bug, not an API response.
	if (!(e instanceof ApiError)) {
		return 'Något gick fel';
	}
	return overrides?.[e.status] ?? DEFAULT_MESSAGES[e.status] ?? 'Något gick fel';
}

/**
 * Maps a 422 response's issues to dotted field keys, e.g. `'names.2'` or
 * `'member_number'`, with the issue's (English) `msg`. Forms use the keys to
 * show their own Swedish message on the right field.
 */
export function fieldErrors(e: unknown): Record<string, string> {
	if (!(e instanceof ApiError) || e.status !== 422 || !Array.isArray(e.detail)) {
		return {};
	}
	const errors: Record<string, string> = {};
	for (const issue of e.detail) {
		const loc = issue.loc[0] === 'body' ? issue.loc.slice(1) : issue.loc;
		const key = loc.join('.');
		// Keep the first issue per field.
		errors[key] ??= issue.msg;
	}
	return errors;
}
