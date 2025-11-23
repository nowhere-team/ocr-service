import { nanoid } from 'nanoid'

import type { Cache } from '@/platform/cache'
import type { Logger } from '@/platform/logger'
import type { OCREngines } from '@/platform/ocr-engines'
import type { Storage } from '@/platform/storage'
import type { ImagesRepository } from '@/repositories/images'
import type { RecognitionsRepository } from '@/repositories/recognitions'
import { readBarcodes, type ReaderOptions, type Position } from 'zxing-wasm'
import type { EventBus } from '@/platform/events'
import sharp from "sharp"

export interface ProcessorConfig {
    confidenceThresholdHigh: number
    confidenceThresholdLow: number
    debugMode: boolean
}

export interface ProcessorResult {
    raw: string
    confidence: number
    engine: 'tesseract' | 'paddleocr'
    aligned: boolean
    usedPreprocessed: boolean
}

export interface RecognitionResult {
    resultType: 'text' | 'qr'
    text?: {
        raw: string
        confidence: number
        engine: 'tesseract' | 'paddleocr'
        aligned: boolean
        usedPreprocessed: boolean
    }
    qr?: {
        data: string
        format: 'fiscal' | 'url' | 'unknown'
        location: { x: number; y: number; width: number; height: number }
        foundInPreprocessed: boolean
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
        private eventBus: EventBus,
        private config: ProcessorConfig,
        private logger: Logger,
    ) {}

    async process(
        imageId: string,
        recognitionId: string,
        acceptedQrFormats?: Array<'fiscal' | 'url' | 'unknown'>,
        alignmentMode?: 'classic' | 'neural',
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

            if (this.config.debugMode) {
                const originalKey = `debug/${recognitionId}/00_original.jpg`
                await this.storage.putObject(originalKey, imageBuffer, 'image/jpeg')

                await this.eventBus.publish('ocr:events', 'ocr.debug.step', {
                    recognitionId,
                    imageId,
                    step: 'original',
                    stepNumber: 0,
                    imageKey: originalKey,
                    description: 'original uploaded image',
                })
            }

            let alignmentResult: { warped: Buffer; preprocessed: Buffer }

            try {
                alignmentResult = await this.engines.aligner.align(imageBuffer, {
                    mode: alignmentMode,
                    applyOcrPrep: false,
                    debugMode: this.config.debugMode,
                    recognitionId,
                    imageId,
                })

                const warpedKey = `${nanoid()}-aligned.jpg`
                const processedUrl = await this.storage.putObject(warpedKey, alignmentResult.warped, 'image/jpeg')
                await this.imagesRepo.update(imageId, {
                    processedUrl: processedUrl,
                })

                this.logger.debug('alignment completed, both versions saved')

                if (this.config.debugMode) {
                    // publish warped version
                    const gatewayWarpedKey = `debug/${recognitionId}/50_aligned_warped.jpg`
                    await this.storage.putObject(gatewayWarpedKey, alignmentResult.warped, 'image/jpeg')

                    await this.eventBus.publish('ocr:events', 'ocr.debug.step', {
                        recognitionId,
                        imageId,
                        step: 'aligned_warped',
                        stepNumber: 50,
                        imageKey: gatewayWarpedKey,
                        description: 'warped version ready for qr scanning and ocr',
                    })

                    // publish preprocessed version
                    const gatewayPrepKey = `debug/${recognitionId}/51_aligned_preprocessed.jpg`
                    await this.storage.putObject(gatewayPrepKey, alignmentResult.preprocessed, 'image/jpeg')

                    await this.eventBus.publish('ocr:events', 'ocr.debug.step', {
                        recognitionId,
                        imageId,
                        step: 'aligned_preprocessed',
                        stepNumber: 51,
                        imageKey: gatewayPrepKey,
                        description: 'preprocessed version for fallback ocr',
                    })
                }

            } catch (error) {
                this.logger.warn('aligner failed, using original with local preprocessing', { error })

                const localPreprocessed = await this.applyLocalPreprocessing(imageBuffer)

                alignmentResult = {
                    warped: imageBuffer,
                    preprocessed: localPreprocessed,
                }

                if (this.config.debugMode) {
                    const fallbackWarpedKey = `debug/${recognitionId}/50_fallback_original.jpg`
                    await this.storage.putObject(fallbackWarpedKey, imageBuffer, 'image/jpeg')

                    await this.eventBus.publish('ocr:events', 'ocr.debug.step', {
                        recognitionId,
                        imageId,
                        step: 'fallback_original',
                        stepNumber: 50,
                        imageKey: fallbackWarpedKey,
                        description: 'alignment failed - using original',
                    })

                    const fallbackPrepKey = `debug/${recognitionId}/51_fallback_preprocessed.jpg`
                    await this.storage.putObject(fallbackPrepKey, localPreprocessed, 'image/jpeg')

                    await this.eventBus.publish('ocr:events', 'ocr.debug.step', {
                        recognitionId,
                        imageId,
                        step: 'fallback_preprocessed',
                        stepNumber: 51,
                        imageKey: fallbackPrepKey,
                        description: 'local preprocessing applied (adaptive threshold)',
                    })
                }
            }

            const qrResult = await this.tryExtractQrFromBothVersions(
                alignmentResult.warped,
                alignmentResult.preprocessed,
                recognitionId,
            )

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
                        foundInPreprocessed: qrResult.foundInPreprocessed,
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

            const textResult = await this.recognizeTextWithStrategy(
                alignmentResult.warped,
                alignmentResult.preprocessed,
                recognitionId,
            )
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
                usedPreprocessed: textResult.usedPreprocessed,
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

    private async tryExtractQrFromBothVersions(
        warpedBuffer: Buffer,
        preprocessedBuffer: Buffer,
        _recognitionId: string,
    ): Promise<{ data: string; format: 'fiscal' | 'url' | 'unknown'; location: any; foundInPreprocessed: boolean } | null> {
        const buffers = [
            { name: 'warped', buffer: warpedBuffer, isPreprocessed: false },
            { name: 'preprocessed', buffer: preprocessedBuffer, isPreprocessed: true },
        ]

        for (const { name, buffer, isPreprocessed } of buffers) {
            try {
                const readerOptions: ReaderOptions = {
                    formats: ['QRCode'],
                    tryHarder: true,
                    maxNumberOfSymbols: 255,
                }

                const results = await readBarcodes(buffer, readerOptions)

                if (results.length === 0) {
                    this.logger.debug(`no qr codes found in ${name}`)
                    continue
                }

                this.logger.debug(`qr codes found in ${name}`, {
                    count: results.length,
                    formats: results.map(r => this.classifyQrFormat(r.text)),
                })

                for (const result of results) {
                    const format = this.classifyQrFormat(result.text)

                    if (format === 'fiscal') {
                        this.logger.info(`fiscal qr code found in ${name}`)

                        return {
                            data: result.text,
                            format,
                            location: this.convertPosition(result.position),
                            foundInPreprocessed: isPreprocessed,
                        }
                    }
                }

                this.logger.info(`no fiscal qr found in ${name}, using first available`, {
                    selectedFormat: this.classifyQrFormat(results[0]!.text),
                })

                return {
                    data: results[0]!.text,
                    format: this.classifyQrFormat(results[0]!.text),
                    location: this.convertPosition(results[0]!.position),
                    foundInPreprocessed: isPreprocessed,
                }
            } catch (error) {
                this.logger.debug(`qr extraction failed for ${name}`, { error })
            }
        }

        return null
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

    private async recognizeTextWithStrategy(
        warpedBuffer: Buffer,
        preprocessedBuffer: Buffer,
        recognitionId: string,
    ): Promise<ProcessorResult> {
        const attempts = [
            {
                name: 'tesseract+preprocessed',
                buffer: preprocessedBuffer,
                engine: this.engines.tesseract,
                usedPreprocessed: true
            },
            {
                name: 'paddleocr+preprocessed',
                buffer: preprocessedBuffer,
                engine: this.engines.paddleocr,
                usedPreprocessed: true
            },
            {
                name: 'paddleocr+warped',
                buffer: warpedBuffer,
                engine: this.engines.paddleocr,
                usedPreprocessed: false
            },
        ]

        let lastResult: ProcessorResult | null = null

        for (const attempt of attempts) {
            try {
                const result = await attempt.engine.recognize(attempt.buffer)

                lastResult = {
                    raw: result.text,
                    confidence: result.confidence,
                    engine: attempt.engine === this.engines.tesseract ? 'tesseract' : 'paddleocr',
                    aligned: true,
                    usedPreprocessed: attempt.usedPreprocessed,
                }

                this.logger.debug(`${attempt.name} completed`, {
                    confidence: result.confidence,
                    threshold: this.config.confidenceThresholdLow,
                })

                if (result.confidence >= this.config.confidenceThresholdLow) {
                    this.logger.info(`${attempt.name} succeeded`, {
                        confidence: result.confidence,
                    })

                    if (this.config.debugMode) {
                        const winnerKey = `debug/${recognitionId}/60_ocr_winner_${attempt.engine}.jpg`
                        await this.storage.putObject(winnerKey, attempt.buffer, 'image/jpeg')

                        await this.eventBus.publish('ocr:events', 'ocr.debug.step', {
                            recognitionId,
                            imageId: '',
                            step: 'ocr_winner',
                            stepNumber: 60,
                            imageKey: winnerKey,
                            description: `winner: ${attempt.name} (${(result.confidence * 100).toFixed(1)}%)`,
                            metadata: {
                                engine: lastResult.engine,
                                confidence: result.confidence,
                                usedPreprocessed: attempt.usedPreprocessed,
                                textLength: result.text.length,
                            },
                        })
                    }

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
                usedPreprocessed: lastResult.usedPreprocessed,
                threshold: this.config.confidenceThresholdLow,
            })

            if (this.config.debugMode) {
                const fallbackKey = `debug/${recognitionId}/61_ocr_fallback_${lastResult.engine}.jpg`
                const fallbackBuffer = lastResult.usedPreprocessed ? preprocessedBuffer : warpedBuffer
                await this.storage.putObject(fallbackKey, fallbackBuffer, 'image/jpeg')

                await this.eventBus.publish('ocr:events', 'ocr.debug.step', {
                    recognitionId,
                    imageId: '',
                    step: 'ocr_fallback',
                    stepNumber: 61,
                    imageKey: fallbackKey,
                    description: `fallback: low confidence (${(lastResult.confidence * 100).toFixed(1)}%)`,
                    metadata: {
                        engine: lastResult.engine,
                        confidence: lastResult.confidence,
                        usedPreprocessed: lastResult.usedPreprocessed,
                        textLength: lastResult.raw.length,
                    },
                })
            }

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

    private async applyLocalPreprocessing(buffer: Buffer): Promise<Buffer> {
        try {
            const preprocessed = await sharp(buffer)
                .grayscale()
                .normalize()
                .threshold(128, { grayscale: true })
                .jpeg({ quality: 95 })
                .toBuffer()

            this.logger.debug('local preprocessing applied')
            return preprocessed
        } catch (error) {
            this.logger.error('local preprocessing failed', { error })
            return buffer
        }
    }
}