import { Jimp } from 'jimp'
import jsQR from 'jsqr'
import { nanoid } from 'nanoid'

import type { Cache } from '@/platform/cache'
import type { Logger } from '@/platform/logger'
import type { OCREngines } from '@/platform/ocr-engines'
import type { Storage } from '@/platform/storage'
import type { ImagesRepository } from '@/repositories/images'
import type { RecognitionsRepository } from '@/repositories/recognitions'

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
        acceptedQrFormats?: Array<'fiscal' | 'url' | 'unknown'>
    ): Promise<RecognitionResult> {
        const startTime = Date.now()

        this.logger.info('processing recognition', {
            imageId,
            recognitionId,
            acceptedQrFormats
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
			const image = await Jimp.read(buffer)
			const { width, height, data } = image.bitmap

			const code = jsQR(new Uint8ClampedArray(data), width, height)

			if (!code) return null

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
        // try 1: clean tesseract
        try {
            const result = await this.engines.tesseract.recognize(buffer)

            if (result.confidence >= this.config.confidenceThresholdHigh) {
                this.logger.info('tesseract succeeded with high confidence', {
                    confidence: result.confidence,
                })
                return { ...result, raw: result.text, engine: 'tesseract', aligned: false }
            }

            this.logger.debug('tesseract confidence too low', {
                confidence: result.confidence,
                threshold: this.config.confidenceThresholdHigh,
            })
        } catch (error) {
            this.logger.warn('tesseract failed, will try aligner + tesseract', { error })
        }

        // try 2: aligner + tesseract
        let alignedBuffer: Buffer | null = null
        try {
            alignedBuffer = await this.engines.aligner.align(buffer)

            const alignedKey = `${nanoid()}-aligned.jpg`
            await this.storage.putObject(alignedKey, alignedBuffer, 'image/jpeg')

            await this.imagesRepo.update(imageId, {
                processedUrl: `minio://${alignedKey}`,
            })

            const result = await this.engines.tesseract.recognize(alignedBuffer)

            if (result.confidence >= this.config.confidenceThresholdLow) {
                this.logger.info('tesseract + aligner succeeded', {
                    confidence: result.confidence,
                })
                return { ...result, raw: result.text, engine: 'tesseract', aligned: true }
            }

            this.logger.debug('tesseract + aligner confidence still low', {
                confidence: result.confidence,
                threshold: this.config.confidenceThresholdLow,
            })
        } catch (error) {
            this.logger.warn('aligner + tesseract failed, will try aligner + paddleocr', { error })
        }

        // try 3: aligner + paddleocr
        try {
            const imageToRecognize = alignedBuffer || buffer
            const result = await this.engines.paddleocr.recognize(imageToRecognize)

            if (alignedBuffer) {
                this.logger.info('paddleocr + aligner succeeded', {
                    confidence: result.confidence,
                })
                return { ...result, raw: result.text, engine: 'paddleocr', aligned: true }
            } else {
                // if aligner got down previously, try again for paddle
                try {
                    alignedBuffer = await this.engines.aligner.align(buffer)

                    // if there's no saved version
                    const image = await this.imagesRepo.findById(imageId)
                    if (!image?.processedUrl) {
                        const alignedKey = `${nanoid()}-aligned.jpg`
                        await this.storage.putObject(alignedKey, alignedBuffer, 'image/jpeg')
                        await this.imagesRepo.update(imageId, {
                            processedUrl: `minio://${alignedKey}`,
                        })
                    }

                    const alignedResult = await this.engines.paddleocr.recognize(alignedBuffer)

                    this.logger.info('paddleocr + aligner succeeded (second attempt)', {
                        confidence: alignedResult.confidence,
                    })
                    return { ...alignedResult, raw: alignedResult.text, engine: 'paddleocr', aligned: true }
                } catch (alignError) {
                    this.logger.debug('aligner failed for paddleocr, using original result', {
                        error: alignError
                    })
                    // возвращаем результат с оригинальным изображением
                    return { ...result, raw: result.text, engine: 'paddleocr', aligned: false }
                }
            }
        } catch (error) {
            this.logger.warn('aligner + paddleocr failed, will try pure paddleocr', { error })
        }

        // try 4: clean paddleocr as last resort
        try {
            const result = await this.engines.paddleocr.recognize(buffer)

            this.logger.info('pure paddleocr succeeded as fallback', {
                confidence: result.confidence,
            })

            return { ...result, raw: result.text, engine: 'paddleocr', aligned: false }
        } catch (error) {
            this.logger.error('all ocr engines failed', { error })
            throw new Error('all ocr engines unavailable, unable to recognize')
        }
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
