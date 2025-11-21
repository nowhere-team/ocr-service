import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { inspectRoutes } from 'hono/dev'

import type { Logger } from '@/platform/logger'
import type { Services } from '@/services'

import { inject } from './middleware/inject'
import { registerRoutes } from './routes'
import type { ExternalDependencies } from './types'

export interface ServerConfig {
	port: number
	development: boolean
}

export interface Server {
	instance: Bun.Server<any>
	router: ReturnType<typeof createRouter>
}

export function createRouter(deps: ExternalDependencies) {
	const app = new Hono().use('*', cors()).use('*', inject(deps)).route('/', registerRoutes())

	const routes = inspectRoutes(app)
	deps.logger.debug('routes registered', {
		count: routes.length,
		routes: routes
			.filter((r: { method: string; path: string }) => r.method !== 'ALL')
			.map(r => `${r.method} ${r.path}`),
	})

	return app
}

export function createServer(logger: Logger, services: Services, config: ServerConfig): Server {
	const router = createRouter({ logger, services, config })

	const instance = Bun.serve({
		port: config.port,
		fetch: router.fetch,
	})

	return { instance, router }
}
