import ky, { type KyInstance } from 'ky'

import type { Logger } from '@/platform/logger'

export interface TesseractConfig {
	url: string
	timeout: number
}

export interface TesseractResult {
	text: string
	confidence: number
}

export class TesseractClient {
	private readonly api: KyInstance

	constructor(
		private readonly logger: Logger,
		private readonly config: TesseractConfig,
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
						this.logger.debug('tesseract request starting', {
							url: request.url,
						})
					},
				],
				beforeError: [
					error => {
						const { request, response } = error
						this.logger.error('tesseract request failed', {
							url: request.url,
							status: response?.status,
							statusText: response?.statusText,
						})
						return error
					},
				],
				afterResponse: [
					(_request, _options, response) => {
						this.logger.debug('tesseract response received', {
							status: response.status,
						})
					},
				],
			},
		})
	}

	async recognize(buffer: Buffer, lang: string = 'rus+eng'): Promise<TesseractResult> {
		const startTime = Date.now()

		try {
			const formData = new FormData()
			formData.append('image', new Blob([buffer]))

			const searchParams = new URLSearchParams()
			searchParams.set('lang', lang)

			const response = await this.api
				.post('api/v1/recognize', {
					body: formData,
					searchParams,
				})
				.json<TesseractResult>()

			const duration = Date.now() - startTime

			this.logger.info('tesseract recognition completed', {
				confidence: response.confidence,
				textLength: response.text.length,
				language: lang,
				duration,
			})

			return response
		} catch (error) {
			const duration = Date.now() - startTime

			this.logger.error('tesseract recognition failed', {
				error,
				duration,
			})

			throw new Error(`tesseract service unavailable: ${error instanceof Error ? error.message : 'unknown error'}`)
		}
	}
}
