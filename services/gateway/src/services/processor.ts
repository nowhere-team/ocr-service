import { Jimp } from 'jimp'
import jsQR from 'jsqr'
import { nanoid } from 'nanoid'

import type { Cache } from '@/platform/cache'
import type { Logger } from '@/platform/logger'
import type { Storage } from '@/platform/storage'
import type { ImagesRepository } from '@/repositories/images'
import type { RecognitionsRepository } from '@/repositories/recognitions'

export interface ProcessorConfig {
	tesseractUrl: string
	paddleocrUrl: string
	alignerUrl: string
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
		private config: ProcessorConfig,
		private logger: Logger,
	) {}

	async process(imageId: string, recognitionId: string): Promise<RecognitionResult> {
		const startTime = Date.now()

		this.logger.info('processing recognition', { imageId, recognitionId })

		// update status to processing
		await this.recognitionsRepo.update(recognitionId, {
			status: 'processing',
		})

		// get image from cache or storage
		const imageBuffer = await this.getImageBuffer(imageId)

		// try to extract qr first
		const qrResult = await this.tryExtractQr(imageBuffer)

		if (qrResult) {
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

			this.logger.info('qr code extracted', {
				recognitionId,
				format: qrResult.format,
				processingTime,
			})

			return {
				resultType: 'qr',
				qr: qrResult,
				processingTime,
			}
		}

		// no qr found, try ocr
		const textResult = await this.recognizeText(imageBuffer, imageId)
		const processingTime = Date.now() - startTime

		await this.recognitionsRepo.update(recognitionId, {
			status: 'completed',
			resultType: 'text',
			rawText: textResult.raw,
			confidence: textResult.confidence,
			engine: textResult.engine,
			alignerUsed: textResult.aligned,
			processingTime,
			completedAt: new Date(),
		})

		this.logger.info('text recognized', {
			recognitionId,
			engine: textResult.engine,
			confidence: textResult.confidence,
			alignerUsed: textResult.aligned,
			processingTime,
		})

		return {
			resultType: 'text',
			text: textResult,
			processingTime,
		}
	}

	private async getImageBuffer(imageId: string): Promise<Buffer> {
		const image = await this.imagesRepo.findById(imageId)
		if (!image) {
			throw new Error('image not found')
		}

		// try cache first
		const cacheKey = `ocr:image:${imageId}`
		const cached = await this.cache.getBuffer(cacheKey)
		if (cached) {
			return cached
		}

		// load from storage
		const key = image.originalUrl.replace('minio://', '').split('/').slice(1).join('/')
		return await this.storage.getObject(key)
	}

	private async tryExtractQr(
		buffer: Buffer,
	): Promise<{ data: string; format: 'fiscal' | 'url' | 'unknown'; location: any } | null> {
		try {
			const image = await Jimp.read(buffer)
			const { width, height, data } = image.bitmap

			const code = jsQR(new Uint8ClampedArray(data), width, height)

			if (!code) return null

			// determine format
			let format: 'fiscal' | 'url' | 'unknown' = 'unknown'
			if (code.data.includes('fn=') || code.data.startsWith('t=')) {
				format = 'fiscal'
			} else if (code.data.startsWith('http')) {
				format = 'url'
			}

			return {
				data: code.data,
				format,
				location: code.location,
			}
		} catch (error) {
			this.logger.debug('qr extraction failed', { error })
			return null
		}
	}

	private async recognizeText(buffer: Buffer, imageId: string): Promise<ProcessorResult> {
		// attempt 1: tesseract
		let result: any = await this.callTesseract(buffer)

		if (result.confidence >= this.config.confidenceThresholdHigh) {
			return { ...result, alignerUsed: false }
		}

		this.logger.debug('tesseract confidence low, trying aligner', {
			confidence: result.confidence,
		})

		// attempt 2: aligner + tesseract
		const alignedBuffer = await this.callAligner(buffer)

		// save aligned image to storage
		const alignedKey = `${nanoid()}-aligned.jpg`
		await this.storage.putObject(alignedKey, alignedBuffer, 'image/jpeg')

		// update image record with processed url
		await this.imagesRepo.update(imageId, {
			processedUrl: `minio://${alignedKey}`,
		})

		result = await this.callTesseract(alignedBuffer)

		if (result.confidence >= this.config.confidenceThresholdLow) {
			return { ...result, aligned: true }
		}

		this.logger.debug('tesseract+aligner confidence low, trying paddleocr', {
			confidence: result.confidence,
		})

		// attempt 3: paddleocr
		result = await this.callPaddleOCR(buffer)

		return { ...result, aligned: false }
	}

	private async callTesseract(buffer: Buffer): Promise<{ raw: string; confidence: number; engine: 'tesseract' }> {
		const formData = new FormData()
		formData.append('image', new Blob([buffer]))

		const response = await fetch(`${this.config.tesseractUrl}/recognize`, {
			method: 'POST',
			body: formData,
		})

		if (!response.ok) {
			throw new Error(`tesseract error: ${response.status}`)
		}

		const data = (await response.json()) as any

		return {
			raw: data.text,
			confidence: data.confidence,
			engine: 'tesseract',
		}
	}

	private async callAligner(buffer: Buffer): Promise<Buffer> {
		const formData = new FormData()
		formData.append('image', new Blob([buffer]))

		const response = await fetch(`${this.config.alignerUrl}/align`, {
			method: 'POST',
			body: formData,
		})

		if (!response.ok) {
			throw new Error(`aligner error: ${response.status}`)
		}

		return Buffer.from(await response.arrayBuffer())
	}

	private async callPaddleOCR(buffer: Buffer): Promise<{ raw: string; confidence: number; engine: 'paddleocr' }> {
		const formData = new FormData()
		formData.append('image', new Blob([buffer]))

		const response = await fetch(`${this.config.paddleocrUrl}/recognize`, {
			method: 'POST',
			body: formData,
		})

		if (!response.ok) {
			throw new Error(`paddleocr error: ${response.status}`)
		}

		const data = (await response.json()) as any

		return {
			raw: data!.text,
			confidence: data!.confidence,
			engine: 'paddleocr',
		}
	}
}
