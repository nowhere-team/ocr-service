import ky, { type KyInstance } from 'ky'

import type { Logger } from '@/platform/logger'

export interface PaddleOCRConfig {
	url: string
	timeout: number
}

export interface PaddleOCRResult {
	text: string
	confidence: number
}

export class PaddleOCRClient {
	private readonly api: KyInstance

	constructor(
		private readonly logger: Logger,
		private readonly config: PaddleOCRConfig,
	) {
		this.api = ky.create({
			prefixUrl: config.url,
			timeout: config.timeout,
			retry: {
				limit: 3,
				methods: ['post'],
				statusCodes: [408, 413, 429, 500, 502, 503, 504],
				backoffLimit: 10000,
			},
			hooks: {
				beforeRequest: [
					request => {
						this.logger.debug('paddleocr request starting', {
							url: request.url,
						})
					},
				],
				beforeError: [
					error => {
						const { request, response } = error
						this.logger.error('paddleocr request failed', {
							url: request.url,
							status: response?.status,
							statusText: response?.statusText,
						})
						return error
					},
				],
				afterResponse: [
					(_request, _options, response) => {
						this.logger.debug('paddleocr response received', {
							status: response.status,
						})
					},
				],
			},
		})
	}

	async recognize(buffer: Buffer): Promise<PaddleOCRResult> {
		const startTime = Date.now()

		try {
			const formData = new FormData()
			formData.append('file', new Blob([buffer]))

			const response = await this.api.post('api/v1/recognize', { body: formData }).json<PaddleOCRResult>()

			const duration = Date.now() - startTime

			this.logger.info('paddleocr recognition completed', {
				confidence: response.confidence,
				textLength: response.text.length,
				duration,
			})

			return response
		} catch (error) {
			const duration = Date.now() - startTime

			this.logger.error('paddleocr recognition failed', {
				error,
				duration,
			})

			throw new Error(`paddleocr service unavailable: ${error instanceof Error ? error.message : 'unknown error'}`)
		}
	}
}
