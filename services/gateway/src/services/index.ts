import type { Cache } from '@/platform/cache'
import type { Database } from '@/platform/database'
import type { Logger } from '@/platform/logger'
import type { OCREngines } from '@/platform/ocr-engines'
import type { Queue } from '@/platform/queue'
import type { Storage } from '@/platform/storage'
import { createRepositories } from '@/repositories'

import { OcrService } from './ocr'
import { type ProcessorConfig, RecognitionProcessor } from './processor.ts'

export interface Services {
	ocr: OcrService
	processor: RecognitionProcessor
}

export function createServices(
	db: Database,
	cache: Cache,
	storage: Storage,
	engines: OCREngines,
	queue: Queue,
	logger: Logger,
	processorConfig: ProcessorConfig,
): Services {
	const repos = createRepositories(db, cache, logger)

	const ocr = new OcrService(repos.images, repos.recognitions, storage, cache, queue, logger.named('service/ocr'))

	const processor = new RecognitionProcessor(
		repos.images,
		repos.recognitions,
		storage,
		cache,
		engines,
		processorConfig,
		logger.named('service/processor'),
	)

	return { ocr, processor }
}
