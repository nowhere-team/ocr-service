export const LOG_LEVELS = ['trace', 'debug', 'info', 'warn', 'error'] as const
export type LogLevel = (typeof LOG_LEVELS)[number]

export const LOG_FORMATS = ['json', 'text'] as const
export type LogFormat = (typeof LOG_FORMATS)[number]

export type LogContext = { [key: string]: unknown } | Error

export interface Logger {
	debug(message: string, context?: LogContext): void

	info(message: string, context?: LogContext): void

	warn(message: string, context?: LogContext): void

	error(message: string, context?: LogContext): void

	child(context: LogContext): Logger

	named(name: string): Logger
}

export interface LoggerConfig {
	name?: string
	level: LogLevel
	format: LogFormat
}
