import { Queue as BullQueue, QueueEvents, type QueueOptions } from 'bullmq'
import Redis from 'ioredis'

import type { Logger } from '@/platform/logger'

export interface QueueConfig {
	url: string
}

export interface RecognitionJob {
	imageId: string
	recognitionId: string
	sourceService?: string
	sourceReference?: string
    acceptedQrFormats?: Array<'fiscal' | 'url' | 'unknown'>
}

let redis: Redis | null = null

export async function createQueue(logger: Logger, config: QueueConfig) {
	redis = new Redis(config.url, {
		maxRetriesPerRequest: null,
		enableReadyCheck: false,
	})

	const queueOptions: QueueOptions = {
		connection: redis,
		defaultJobOptions: {
			attempts: 3,
			backoff: {
				type: 'exponential',
				delay: 2000,
			},
			removeOnComplete: {
				count: 100,
				age: 24 * 3600,
			},
			removeOnFail: {
				count: 1000,
			},
		},
	}

	const instance = new BullQueue<RecognitionJob>('ocr-jobs', queueOptions)
	const events = new QueueEvents('ocr-jobs', { connection: redis })

	logger.info('queue initialized')

	return { instance, events }
}

export async function closeQueue(result: Queue) {
	await result.instance.close()
	await result.events.close()
	if (redis) {
		await redis.quit()
	}
}

export type Queue = Awaited<ReturnType<typeof createQueue>>
