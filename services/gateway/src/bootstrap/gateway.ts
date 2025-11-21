// noinspection DuplicatedCode

import { createServer, type Server } from '@/gateway/index.ts'
import type { Cache } from '@/platform/cache'
import { createCache } from '@/platform/cache'
import type { Config } from '@/platform/config'
import { createConfig } from '@/platform/config'
import type { Database } from '@/platform/database'
import { createDatabase } from '@/platform/database'
import { createEventBus, type EventBus } from '@/platform/events'
import type { Logger } from '@/platform/logger'
import { createLogger } from '@/platform/logger'
import { closeQueue, createQueue, type Queue } from '@/platform/queue'
import type { Storage } from '@/platform/storage'
import { createStorage } from '@/platform/storage'
import type { Services } from '@/services'
import { createServices } from '@/services'

export interface GatewayApp {
	config: Config
	logger: Logger
	database: Database
	cache: Cache
	storage: Storage
	queue: Queue
	eventBus: EventBus
	services: Services
	server: Server
}

export async function startGateway(): Promise<GatewayApp> {
	const config = createConfig(process.env)
	const logger = createLogger({ format: config.LOG_FORMAT, level: config.LOG_LEVEL })
	logger.info('starting ocr gateway', { env: config.NODE_ENV })

	const database = await createDatabase(logger, { url: config.DATABASE_URL })
	logger.info('database initialized')

	const cache = await createCache(logger, {
		url: config.REDIS_URL,
		keyPrefix: 'ocr',
	})
	logger.info('cache initialized')

	const storage = await createStorage(logger, {
		endpoint: config.MINIO_ENDPOINT,
		port: config.MINIO_PORT,
		accessKey: config.MINIO_ACCESS_KEY,
		secretKey: config.MINIO_SECRET_KEY,
		useSSL: config.MINIO_USE_SSL,
		bucket: config.MINIO_BUCKET,
	})
	logger.info('storage initialized')

	const queue = await createQueue(logger, { url: config.REDIS_URL })
	logger.info('queue initialized')

	const eventBus = await createEventBus(logger, { url: config.REDIS_URL })
	logger.info('event bus initialized')

	const services = createServices(
		database,
		cache,
		storage,
		{
			tesseractUrl: config.TESSERACT_URL,
			paddleocrUrl: config.PADDLEOCR_URL,
			alignerUrl: config.ALIGNER_URL,
			confidenceThresholdHigh: config.CONFIDENCE_THRESHOLD_HIGH,
			confidenceThresholdLow: config.CONFIDENCE_THRESHOLD_LOW,
		},
		logger,
	)
	logger.info('services initialized')

	// subscribe to queue events to publish to eventbus
	queue.events.on('added', async ({ jobId }) => {
		try {
			const job = await queue.instance.getJob(jobId)

			if (!job) {
				logger.warn('job not found', { jobId })
				return
			}

			const position = await queue.instance.getWaitingCount()

			await eventBus.publish('ocr:events', 'ocr.queued', {
				imageId: job.data.imageId,
				recognitionId: job.data.recognitionId,
				sourceService: job.data.sourceService,
				sourceReference: job.data.sourceReference,
				position,
				estimatedWait: position * 15,
			})
		} catch (error) {
			logger.error('failed to publish queued event', { error, jobId })
		}
	})

	const server = createServer(logger, services, {
		port: config.PORT,
		development: config.isDev(),
	})
	logger.info('http server started', { port: config.PORT })

	logger.info('ocr gateway is ready')

	return { config, logger, database, cache, storage, queue, eventBus, services, server }
}

export async function stopGateway(app: GatewayApp) {
	app.logger.info('shutting down ocr gateway')

	await app.server.instance.stop()
	await app.eventBus.close()
	await closeQueue(app.queue)

	app.logger.info('ocr gateway stopped')
}
