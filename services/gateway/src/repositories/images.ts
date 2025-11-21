import { eq } from 'drizzle-orm'

import type { Cache } from '@/platform/cache'
import type { Database } from '@/platform/database'
import { images } from '@/platform/database/schema'
import type { Logger } from '@/platform/logger'

export interface CreateImageDto {
	originalUrl: string
	fileSize: number
	mimeType: string
	width?: number
	height?: number
	sourceService?: string
	sourceReference?: string
	processedUrl?: string
}

export class ImagesRepository {
	constructor(
		private db: Database,
		private cache: Cache,
		private logger: Logger,
	) {}

	async create(dto: CreateImageDto) {
		const [image] = await this.db.insert(images).values(dto).returning()

		this.logger.debug('image created', { imageId: image!.id })

		return image!
	}

	async findById(imageId: string) {
		const cacheKey = `image:${imageId}`
		const cached = await this.cache.get(cacheKey)
		if (cached) {
			return JSON.parse(cached)
		}

		const image = await this.db.query.images.findFirst({
			where: eq(images.id, imageId),
		})

		if (image) {
			await this.cache.set(cacheKey, JSON.stringify(image), 3600)
		}

		return image || null
	}

	async update(imageId: string, data: Partial<CreateImageDto>) {
		const [image] = await this.db.update(images).set(data).where(eq(images.id, imageId)).returning()

		await this.cache.delete(`image:${imageId}`)

		this.logger.debug('image updated', { imageId })

		return image
	}
}
