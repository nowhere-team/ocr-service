import type { Logger } from '@/platform/logger'
import type { Services } from '@/services'

export interface ServerConfig {
	port: number
	development: boolean
}

export interface ExternalDependencies {
	logger: Logger
	services: Services
	config: ServerConfig
}

declare module 'hono' {
	// eslint-disable-next-line
	interface ContextVariableMap extends ExternalDependencies {}
}
