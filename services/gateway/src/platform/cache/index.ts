import Redis from 'ioredis'

import type { Logger } from '@/platform/logger'

export interface Cache {
	get(key: string): Promise<string | null>
	set(key: string, value: string, ttl?: number): Promise<void>
	getBuffer(key: string): Promise<Buffer | null>
	setBuffer(key: string, value: Buffer, ttl?: number): Promise<void>
	delete(key: string): Promise<void>
	exists(key: string): Promise<boolean>
}

export interface CacheConfig {
	url: string
	keyPrefix?: string
}

class RedisCache implements Cache {
	constructor(
		private client: Redis,
		private logger: Logger,
		private keyPrefix: string = '',
	) {}

	private prefixKey(key: string): string {
		return this.keyPrefix ? `${this.keyPrefix}:${key}` : key
	}

	async get(key: string): Promise<string | null> {
		const prefixed = this.prefixKey(key)
		return this.client.get(prefixed)
	}

	async set(key: string, value: string, ttl?: number): Promise<void> {
		const prefixed = this.prefixKey(key)
		if (ttl) {
			await this.client.setex(prefixed, ttl, value)
		} else {
			await this.client.set(prefixed, value)
		}
	}

	async getBuffer(key: string): Promise<Buffer | null> {
		const prefixed = this.prefixKey(key)
		return this.client.getBuffer(prefixed)
	}

	async setBuffer(key: string, value: Buffer, ttl?: number): Promise<void> {
		const prefixed = this.prefixKey(key)
		if (ttl) {
			await this.client.setex(prefixed, ttl, value)
		} else {
			await this.client.set(prefixed, value)
		}
	}

	async delete(key: string): Promise<void> {
		const prefixed = this.prefixKey(key)
		await this.client.del(prefixed)
	}

	async exists(key: string): Promise<boolean> {
		const prefixed = this.prefixKey(key)
		const result = await this.client.exists(prefixed)
		return result === 1
	}
}

export async function createCache(logger: Logger, config: CacheConfig): Promise<Cache> {
	const client = new Redis(config.url, {
		maxRetriesPerRequest: null,
		enableReadyCheck: false,
	})

	await client.ping()

	logger.info('cache initialized', { url: config.url })

	return new RedisCache(client, logger.named('cache'), config.keyPrefix)
}
