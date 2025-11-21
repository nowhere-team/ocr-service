import js from '@eslint/js'
import prettierConfig from 'eslint-plugin-prettier/recommended'
import importSort from 'eslint-plugin-simple-import-sort'
import globals from 'globals'
import ts from 'typescript-eslint'

export default [
	js.configs.recommended,
	...ts.configs.recommended,
	prettierConfig,
	{
		plugins: {
			'simple-import-sort': importSort,
		},
		languageOptions: {
			globals: {
				...globals.node,
			},
		},
		rules: {
			'simple-import-sort/imports': 'error',
			'simple-import-sort/exports': 'error',
			'no-console': ['warn', { allow: ['error', 'warn'] }],
			'prefer-const': 'error',
			'@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
			'@typescript-eslint/no-explicit-any': 'off',
		},
	},
]
