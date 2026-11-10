import path from 'node:path';
import js from '@eslint/js';
import stylistic from '@stylistic/eslint-plugin';
import svelte from 'eslint-plugin-svelte';
import { defineConfig, includeIgnoreFile } from 'eslint/config';
import globals from 'globals';
import ts from 'typescript-eslint';

const gitignorePath = path.resolve(import.meta.dirname, '.gitignore');

export default defineConfig(
  includeIgnoreFile(gitignorePath),
  {
    // Generated code, never edited by hand: the API types come from
    // openapi-typescript (`npm run generate:types`), the UI components and
    // `cn.ts` from the shadcn-svelte CLI. They follow their generators'
    // style (e.g. double quotes) and must stay updatable with them.
    ignores: [
      'src/lib/types/api.ts',
      'src/lib/components/ui/**',
      'src/lib/utils/cn.ts',
    ],
  },
  js.configs.recommended,
  ts.configs.recommended,
  svelte.configs.recommended,
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    plugins: { '@stylistic': stylistic },
    rules: {
      '@stylistic/quotes': ['error', 'single', { avoidEscape: true }],
      // typescript-eslint strongly recommend that you do not use the no-undef lint rule on TypeScript projects.
      // see: https://typescript-eslint.io/troubleshooting/faqs/eslint/#i-get-errors-from-the-no-undef-rule-about-global-variables-not-being-defined-even-though-there-are-no-typescript-errors
      'no-undef': 'off',
    },
  },
  {
    files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
    languageOptions: {
      parserOptions: {
        projectService: true,
        extraFileExtensions: ['.svelte'],
        parser: ts.parser,
      },
    },
  },
);
