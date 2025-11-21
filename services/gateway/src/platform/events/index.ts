import Redis from 'ioredis'

import type { Logger } from '@/platform/logger'

import { EventBus } from './bus'

let redisSubscriber: Redis | null = null
let redisPublisher: Redis | null = null

export async function createEventBus(logger: Logger, config: { url: string }): Promise<EventBus> {
	redisSubscriber = new Redis(config.url, {
		maxRetriesPerRequest: null,
		enableReadyCheck: false,
	})

	redisPublisher = new Redis(config.url, {
		maxRetriesPerRequest: null,
		enableReadyCheck: false,
	})

	await Promise.all([redisSubscriber.connect(), redisPublisher.connect()])

	logger.info('redis pub/sub clients connected')

	return new EventBus(
		{
			subscriber: redisSubscriber,
			publisher: redisPublisher,
		},
		logger,
	)
}

export async function closeEventBus(eventBus: EventBus) {
	await eventBus.close()
	if (redisSubscriber) await redisSubscriber.quit()
	if (redisPublisher) await redisPublisher.quit()
}

export * from './bus'
export * from './map.ts'
