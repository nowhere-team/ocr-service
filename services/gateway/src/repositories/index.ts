import type { Cache } from '@/platform/cache'
import type { Database } from '@/platform/database'
import type { Logger } from '@/platform/logger'

import { ImagesRepository } from './images'
import { RecognitionsRepository } from './recognitions'

export interface Repositories {
	images: ImagesRepository
	recognitions: RecognitionsRepository
}

export function createRepositories(db: Database, cache: Cache, logger: Logger): Repositories {
	const images = new ImagesRepository(db, cache, logger.named('repository/images'))
	const recognitions = new RecognitionsRepository(db, cache, logger.named('repository/recognitions'))

	return { images, recognitions }
}
