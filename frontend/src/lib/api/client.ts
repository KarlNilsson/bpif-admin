export type Fetch = typeof fetch;

const API_BASE = '/api/v1';

export async function request<T>(fetchFn: Fetch, path: string, init?: RequestInit): Promise<T> {
	const response = await fetchFn(`${API_BASE}${path}`, {
		...init,
		headers: { Accept: 'application/json', ...init?.headers }
	});
	if (!response.ok) {
		throw new Error(`Request to ${path} failed with status ${response.status}`);
	}
	return (await response.json()) as T;
}
