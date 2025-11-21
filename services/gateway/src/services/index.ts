import type { Cache } from '@/platform/cache'
import type { Database } from '@/platform/database'
import type { Logger } from '@/platform/logger'
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
	processorConfig: ProcessorConfig,
	logger: Logger,
): Services {
	const repos = createRepositories(db, cache, logger)

	const ocr = new OcrService(repos.images, repos.recognitions, storage, cache, logger.named('service/ocr'))

	const processor = new RecognitionProcessor(
		repos.images,
		repos.recognitions,
		storage,
		cache,
		processorConfig,
		logger.named('service/processor'),
	)

	return { ocr, processor }
}
