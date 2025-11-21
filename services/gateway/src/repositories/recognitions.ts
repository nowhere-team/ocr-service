import { eq } from 'drizzle-orm'

import type { Cache } from '@/platform/cache'
import type { Database } from '@/platform/database'
import { recognitionResults } from '@/platform/database/schema'
import type { Logger } from '@/platform/logger'

export interface CreateRecognitionDto {
	imageId: string
	status: 'queued' | 'processing' | 'completed' | 'failed'
}

export interface UpdateRecognitionDto {
	status?: 'queued' | 'processing' | 'completed' | 'failed'
	resultType?: 'text' | 'qr'
	rawText?: string
	confidence?: number
	engine?: 'tesseract' | 'paddleocr'
	aligned?: boolean
	qrData?: string
	qrFormat?: 'fiscal' | 'url' | 'unknown'
	qrLocation?: { x: number; y: number; width: number; height: number }
	processingTime?: number
	queueWaitTime?: number
	error?: string
	completedAt?: Date
}

export class RecognitionsRepository {
	constructor(
		private db: Database,
		private cache: Cache,
		private logger: Logger,
	) {}

	async create(dto: CreateRecognitionDto) {
		const [recognition] = await this.db.insert(recognitionResults).values(dto).returning()

		this.logger.debug('recognition created', { recognitionId: recognition!.id })

		return recognition!
	}

	async findById(recognitionId: string) {
		const cacheKey = `recognition:${recognitionId}`
		const cached = await this.cache.get(cacheKey)
		if (cached) {
			return JSON.parse(cached)
		}

		const recognition = await this.db.query.recognitionResults.findFirst({
			where: eq(recognitionResults.id, recognitionId),
		})

		if (recognition) {
			await this.cache.set(cacheKey, JSON.stringify(recognition), 3600)
		}

		return recognition || null
	}

	async update(recognitionId: string, dto: UpdateRecognitionDto) {
		const [recognition] = await this.db
			.update(recognitionResults)
			.set(dto)
			.where(eq(recognitionResults.id, recognitionId))
			.returning()

		await this.cache.delete(`recognition:${recognitionId}`)

		this.logger.debug('recognition updated', { recognitionId })

		return recognition
	}
}
