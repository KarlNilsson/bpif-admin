import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			adapter: adapter({ fallback: 'index.html' })
		})
	],
	server: {
		proxy: {
			'/api': process.env.API_PROXY_TARGET ?? 'http://localhost:8000'
		},
		watch: {
			// File events from a Windows bind mount do not reach the container.
			usePolling: process.env.WATCH_POLLING === 'true'
		}
	}
});
