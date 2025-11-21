import { ApiError, ErrorSeverity } from './base'

export class NotFoundError extends ApiError {
	constructor(message: string = 'resource not found', details?: Record<string, unknown>) {
		super('NOT_FOUND', 404, message, details)
	}
}

export class ValidationError extends ApiError {
	constructor(
		message: string = 'validation error',
		public readonly fields?: Array<{ field: string; message: string; code?: string }>,
		details?: Record<string, unknown>,
	) {
		super('VALIDATION_ERROR', 400, message, details)
	}

	override toResponse() {
		return {
			...super.toResponse(),
			...(this.fields && { fields: this.fields }),
		}
	}
}

export class InternalError extends ApiError {
	override severity = ErrorSeverity.HIGH

	constructor(message: string = 'internal router error', details?: Record<string, unknown>) {
		super('INTERNAL_ERROR', 500, message, details)
	}
}
