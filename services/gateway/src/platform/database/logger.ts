import type { Logger as DrizzleLogger } from 'drizzle-orm/logger'

import type { Logger } from '@/platform/logger'

export class DatabaseLogger implements DrizzleLogger {
	constructor(private readonly logger: Logger) {}

	logQuery(query: string, params: unknown[]): void {
		this.logger.debug(query, { params })
	}
}
