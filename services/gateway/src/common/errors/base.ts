import type { ContentfulStatusCode } from 'hono/utils/http-status'

export enum ErrorSeverity {
	LOW = 1,
	MEDIUM = 2,
	HIGH = 3,
	CRITICAL = 4,
}

export abstract class AppError extends Error {
	protected constructor(message: string) {
		super(message)
		this.name = this.constructor.name
	}
}

export abstract class ApiError extends AppError {
	public readonly severity: ErrorSeverity = ErrorSeverity.LOW

	protected constructor(
		public readonly code: string,
		public readonly status: ContentfulStatusCode,
		message: string,
		public readonly details?: Record<string, unknown>,
	) {
		super(message)
	}

	toResponse() {
		return {
			code: this.code,
			message: this.message,
			...(this.details && { details: this.details }),
			timestamp: new Date().toISOString(),
		}
	}
}
