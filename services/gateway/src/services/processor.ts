import { nanoid } from 'nanoid'

import type { Cache } from '@/platform/cache'
import type { Logger } from '@/platform/logger'
import type { OCREngines } from '@/platform/ocr-engines'
import type { Storage } from '@/platform/storage'
import type { ImagesRepository } from '@/repositories/images'
import type { RecognitionsRepository } from '@/repositories/recognitions'
import { readBarcodes, type ReaderOptions, type Position } from 'zxing-wasm'

export interface ProcessorConfig {
	confidenceThresholdHigh: number
	confidenceThresholdLow: number
}

export interface ProcessorResult {
	raw: string
	confidence: number
	engine: 'tesseract' | 'paddleocr'
	aligned: boolean
}

export interface RecognitionResult {
	resultType: 'text' | 'qr'
	text?: {
		raw: string
		confidence: number
		engine: 'tesseract' | 'paddleocr'
		aligned: boolean
	}
	qr?: {
		data: string
		format: 'fiscal' | 'url' | 'unknown'
		location: { x: number; y: number; width: number; height: number }
	}
	processingTime: number
}

export class RecognitionProcessor {
	constructor(
		private imagesRepo: ImagesRepository,
		private recognitionsRepo: RecognitionsRepository,
		private storage: Storage,
		private cache: Cache,
		private engines: OCREngines,
		private config: ProcessorConfig,
		private logger: Logger,
	) {}

	async process(
		imageId: string,
		recognitionId: string,
		acceptedQrFormats?: Array<'fiscal' | 'url' | 'unknown'>,
	): Promise<RecognitionResult> {
		const startTime = Date.now()

		this.logger.info('processing recognition', {
			imageId,
			recognitionId,
			acceptedQrFormats,
		})

		try {
			await this.recognitionsRepo.update(recognitionId, {
				status: 'processing',
			})

			const imageBuffer = await this.getImageBuffer(imageId)

			// finding qr
			const qrResult = await this.tryExtractQr(imageBuffer)
			if (qrResult) {
				const shouldAcceptQr = !acceptedQrFormats || acceptedQrFormats.includes(qrResult.format)

				if (shouldAcceptQr) {
					const processingTime = Date.now() - startTime

					await this.recognitionsRepo.update(recognitionId, {
						status: 'completed',
						resultType: 'qr',
						qrData: qrResult.data,
						qrFormat: qrResult.format,
						qrLocation: qrResult.location,
						processingTime,
						completedAt: new Date(),
					})

					this.logger.info('qr code extracted and accepted', {
						recognitionId,
						format: qrResult.format,
						processingTime,
					})

					return {
						resultType: 'qr',
						qr: qrResult,
						processingTime,
					}
				} else {
					this.logger.info('qr code found but not accepted, continuing to ocr', {
						recognitionId,
						foundFormat: qrResult.format,
						acceptedFormats: acceptedQrFormats,
					})
				}
			}

			// trying ocr
			const textResult = await this.recognizeText(imageBuffer, imageId)
			const processingTime = Date.now() - startTime

			await this.recognitionsRepo.update(recognitionId, {
				status: 'completed',
				resultType: 'text',
				rawText: textResult.raw,
				confidence: textResult.confidence,
				engine: textResult.engine,
				aligned: textResult.aligned,
				processingTime,
				completedAt: new Date(),
			})

			this.logger.info('text recognized', {
				recognitionId,
				engine: textResult.engine,
				confidence: textResult.confidence,
				aligned: textResult.aligned,
				processingTime,
			})

			return {
				resultType: 'text',
				text: textResult,
				processingTime,
			}
		} catch (error) {
			await this.recognitionsRepo.update(recognitionId, {
				status: 'failed',
				error: (error as Error).message,
				completedAt: new Date(),
			})

			throw error
		}
	}

	private async getImageBuffer(imageId: string): Promise<Buffer> {
		const image = await this.imagesRepo.findById(imageId)
		if (!image) {
			throw new Error('image not found')
		}

		const cacheKey = `ocr:image:${imageId}`
		const cached = await this.cache.getBuffer(cacheKey)
		if (cached) {
			return cached
		}

		const key = image.originalUrl.replace('minio://', '').split('/').slice(1).join('/')
		return await this.storage.getObject(key)
	}

	private async tryExtractQr(
		buffer: Buffer,
	): Promise<{ data: string; format: 'fiscal' | 'url' | 'unknown'; location: any } | null> {
		try {
			const readerOptions: ReaderOptions = {
				formats: ['QRCode'],
				tryHarder: true,
				maxNumberOfSymbols: 255,
			}

			const results = await readBarcodes(buffer, readerOptions)

			if (results.length === 0) {
				this.logger.debug('no qr codes found')
				return null
			}

			this.logger.debug('qr codes found', {
				count: results.length,
				formats: results.map(r => this.classifyQrFormat(r.text)),
			})

			for (const result of results) {
				const format = this.classifyQrFormat(result.text)

				if (format === 'fiscal') {
					this.logger.info('fiscal qr code found')

					return {
						data: result.text,
						format,
						location: this.convertPosition(result.position),
					}
				}
			}

			this.logger.info('no fiscal qr found, using first available', {
				selectedFormat: this.classifyQrFormat(results[0]!.text),
			})

			return {
				data: results[0]!.text,
				format: this.classifyQrFormat(results[0]!.text),
				location: this.convertPosition(results[0]!.position),
			}
		} catch (error) {
			this.logger.debug('qr extraction failed', { error })
			return null
		}
	}

	private classifyQrFormat(data: string): 'fiscal' | 'url' | 'unknown' {
		if (
			data.includes('fn=') ||
			data.includes('&fn=') ||
			(data.includes('t=') && data.includes('s=') && data.includes('fp='))
		) {
			return 'fiscal'
		}

		if (data.startsWith('http://') || data.startsWith('https://')) {
			return 'url'
		}

		return 'unknown'
	}

	private convertPosition(position: Position) {
		return {
			x: Math.round(position.topLeft.x),
			y: Math.round(position.topLeft.y),
			width: Math.round(position.bottomRight.x - position.topLeft.x),
			height: Math.round(position.bottomRight.y - position.topLeft.y),
		}
	}

	private async recognizeText(buffer: Buffer, imageId: string): Promise<ProcessorResult> {
		let alignedBuffer: Buffer | null = null

		try {
			alignedBuffer = await this.engines.aligner.align(buffer, { applyOcrPrep: true })

			const alignedKey = `${nanoid()}-aligned.jpg`
			const processedUrl = await this.storage.putObject(alignedKey, alignedBuffer, 'image/jpeg')
			await this.imagesRepo.update(imageId, {
				processedUrl: processedUrl,
			})

			this.logger.debug('image aligned and saved')
		} catch (error) {
			this.logger.warn('aligner failed', { error })
		}

		const attempts = []

		if (alignedBuffer) {
			attempts.push(
				{ name: 'tesseract+aligned', buffer: alignedBuffer, engine: this.engines.tesseract, aligned: true },
				{ name: 'paddleocr+aligned', buffer: alignedBuffer, engine: this.engines.paddleocr, aligned: true },
			)
		}

		attempts.push({ name: 'paddleocr+original', buffer: buffer, engine: this.engines.paddleocr, aligned: false })

		let lastResult: ProcessorResult | null = null

		for (const attempt of attempts) {
			try {
				const result = await attempt.engine.recognize(attempt.buffer)

				lastResult = {
					raw: result.text,
					confidence: result.confidence,
					engine: attempt.engine === this.engines.tesseract ? 'tesseract' : 'paddleocr',
					aligned: attempt.aligned,
				}

				this.logger.debug(`${attempt.name} completed`, {
					confidence: result.confidence,
					threshold: this.config.confidenceThresholdLow,
				})

				// проверяем порог для ВСЕХ попыток
				if (result.confidence >= this.config.confidenceThresholdLow) {
					this.logger.info(`${attempt.name} succeeded`, {
						confidence: result.confidence,
					})
					return lastResult
				}
			} catch (error) {
				this.logger.warn(`${attempt.name} failed`, { error })
			}
		}

		if (lastResult) {
			this.logger.warn('all attempts returned low confidence, using last result', {
				confidence: lastResult.confidence,
				engine: lastResult.engine,
				aligned: lastResult.aligned,
				threshold: this.config.confidenceThresholdLow,
			})
			return lastResult
		}

		throw new Error('all ocr engines failed')
	}

	async markAsFailed(recognitionId: string, errorMessage: string): Promise<void> {
		await this.recognitionsRepo.update(recognitionId, {
			status: 'failed',
			error: errorMessage,
			completedAt: new Date(),
		})

		this.logger.info('recognition marked as failed', {
			recognitionId,
			error: errorMessage,
		})
	}
}
