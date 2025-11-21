import type { MiddlewareHandler } from 'hono'

import type { Logger } from '@/platform/logger'
import type { Services } from '@/services'

export interface ExternalDependencies {
	logger: Logger
	services: Services
}

export function inject(deps: ExternalDependencies): MiddlewareHandler {
	return async (c, next) => {
		c.set('logger', deps.logger)
		c.set('services', deps.services)
		await next()
	}
}
