import { PinoLogger } from './pino'
import type { Logger, LoggerConfig } from './types.ts'

export function createLogger(config: LoggerConfig): Logger {
	return new PinoLogger(config)
}

export * from './types'
