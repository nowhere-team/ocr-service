// noinspection DuplicatedCode

import type { Worker } from 'bullmq'

import type { Cache } from '@/platform/cache'
import { createCache } from '@/platform/cache'
import type { Config } from '@/platform/config'
import { createConfig } from '@/platform/config'
import type { Database } from '@/platform/database'
import { createDatabase } from '@/platform/database'
import { createEventBus, type EventBus } from '@/platform/events'
import type { Logger } from '@/platform/logger'
import { createLogger } from '@/platform/logger'
import { createOCREngines, type OCREngines } from '@/platform/ocr-engines'
import { closeQueue, createQueue, type Queue } from '@/platform/queue'
import type { Storage } from '@/platform/storage'
import { createStorage } from '@/platform/storage'
import type { Services } from '@/services'
import { createServices } from '@/services'
import { createWorker } from '@/worker/processor'

export interface WorkerApp {
	config: Config
	logger: Logger
	database: Database
	cache: Cache
	storage: Storage
	queue: Queue
	eventBus: EventBus
	engines: OCREngines
	services: Services
	worker: Worker
}

export async function startWorker(): Promise<WorkerApp> {
	const config = createConfig(process.env)
	const logger = createLogger({ format: config.LOG_FORMAT, level: config.LOG_LEVEL })
	logger.info('starting ocr worker', { env: config.NODE_ENV })

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

	const engines = createOCREngines(logger, {
		tesseractUrl: config.TESSERACT_URL,
		paddleocrUrl: config.PADDLEOCR_URL,
		alignerUrl: config.ALIGNER_URL,
		timeout: config.OCR_ENGINE_TIMEOUT,
	})
	logger.info('ocr engines initialized')

	const services = createServices(database, cache, storage, engines, queue, logger, {
		confidenceThresholdHigh: config.CONFIDENCE_THRESHOLD_HIGH,
		confidenceThresholdLow: config.CONFIDENCE_THRESHOLD_LOW,
	})
	logger.info('services initialized')

	const worker = await createWorker(queue, eventBus, services, logger, config.WORKER_CONCURRENCY)
	logger.info('worker initialized', { concurrency: config.WORKER_CONCURRENCY })

	logger.info('ocr worker is ready, waiting for jobs...')

	return { config, logger, database, cache, storage, queue, eventBus, engines, services, worker }
}

export async function stopWorker(app: WorkerApp) {
	app.logger.info('shutting down ocr worker')

	await app.worker.close()
	await app.eventBus.close()
	await closeQueue(app.queue)

	app.logger.info('ocr worker stopped')
}
