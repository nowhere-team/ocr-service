import pino, { type Logger as Pino, type LoggerOptions } from 'pino'
import pinoPretty from 'pino-pretty'

import type { LogContext, Logger, LoggerConfig } from './types'

export class PinoLogger implements Logger {
	private readonly instance: Pino
	private readonly config: LoggerConfig

	constructor(config: LoggerConfig, instance?: Pino) {
		this.config = config
		this.instance = instance ?? this.createPinoInstance(config)
	}

	private createPinoInstance(config: LoggerConfig): Pino {
		const options: LoggerOptions = {
			level: config.level,
		}

		if (config.name) options.name = config.name

		if (config.format === 'text') {
			const stream = pinoPretty({
				colorize: true,
				translateTime: 'yyyy-mm-dd HH:MM:ss',
				ignore: 'pid,hostname',
			})

			return pino(options, stream)
		}

		return pino(options)
	}

	debug(message: string, context?: LogContext): void {
		this.instance.debug(context || {}, message)
	}

	info(message: string, context?: LogContext): void {
		this.instance.info(context || {}, message)
	}

	warn(message: string, context?: LogContext): void {
		this.instance.warn(context || {}, message)
	}

	error(message: string, context?: LogContext): void {
		this.instance.error(context || {}, message)
	}

	child(context: LogContext): Logger {
		return new PinoLogger(this.config, this.instance.child(context))
	}

	named(name: string): Logger {
		return new PinoLogger({ ...this.config, name })
	}
}
