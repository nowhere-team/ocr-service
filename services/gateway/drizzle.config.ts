import { defineConfig } from 'drizzle-kit'

export default defineConfig({
	out: './migrations',
	dialect: 'postgresql',
	schema: './src/platform/database/schema/index.ts',
	dbCredentials: { url: process.env.DATABASE_URL! },
	schemaFilter: 'public',
	tablesFilter: '*',
	migrations: {
		prefix: 'index',
		table: 'schema_version',
		schema: 'public',
	},
	breakpoints: true,
	strict: true,
	verbose: true,
})
