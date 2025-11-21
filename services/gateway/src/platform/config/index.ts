import type { Env } from 'bun'
import { z } from 'zod'

import { LOG_FORMATS, LOG_LEVELS } from '@/platform/logger'

const schema = z.object({
	NODE_ENV: z.enum(['development', 'production']).default('production'),
	PORT: z.coerce.number().min(1).max(65535).default(8080),

	DATABASE_URL: z.url().nonempty().default('postgresql://ocr:password@localhost:5432/ocr'),

	REDIS_URL: z.url().nonempty().default('redis://localhost:6379'),

	MINIO_ENDPOINT: z.url().nonempty().default('localhost'),
	MINIO_PORT: z.coerce.number().min(1).max(65535).default(9000),
	MINIO_ACCESS_KEY: z.string().nonempty().default('minioadmin'),
	MINIO_SECRET_KEY: z.string().nonempty().default('minioadmin'),
	MINIO_USE_SSL: z.boolean().default(true),
	MINIO_BUCKET: z.string().nonempty().default('images'),

	ALIGNER_URL: z.url().nonempty().default('http://aligner:8000'),
	PADDLEOCR_URL: z.url().nonempty().default('http://paddleocr:8001'),
	TESSERACT_URL: z.url().nonempty().default('http://tesseract:8002'),

	CONFIDENCE_THRESHOLD_HIGH: z.coerce.number().default(0.7),
	CONFIDENCE_THRESHOLD_LOW: z.coerce.number().default(0.6),

	WORKER_CONCURRENCY: z.coerce.number().default(1),

	LOG_LEVEL: z.enum(LOG_LEVELS).default('info'),
	LOG_FORMAT: z.enum(LOG_FORMATS).default('json'),
})

export function createConfig(env: Env) {
	return {
		...schema.parse(env),
		isDev() {
			return this.NODE_ENV !== 'production'
		},
		isProd() {
			return this.NODE_ENV === 'production'
		},
	}
}

export type Config = ReturnType<typeof createConfig>
