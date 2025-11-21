import {nanoid} from 'nanoid'

import type {Cache} from '@/platform/cache'
import type {Logger} from '@/platform/logger'
import type {Queue} from '@/platform/queue'
import type {Storage} from '@/platform/storage'
import type {ImagesRepository} from '@/repositories/images'
import type {RecognitionsRepository} from '@/repositories/recognitions'

export interface UploadImageResult {
    imageId: string
    recognitionId: string
    status: 'queued'
}

export class OcrService {
    constructor(
        private imagesRepo: ImagesRepository,
        private recognitionsRepo: RecognitionsRepository,
        private storage: Storage,
        private cache: Cache,
        private queue: Queue,
        private logger: Logger,
    ) {
    }

    async uploadImage(
        file: File,
        metadata?: {
            sourceService?: string;
            sourceReference?: string,
            acceptedQrFormats?: Array<'fiscal' | 'url' | 'unknown'>
        },
    ): Promise<UploadImageResult> {
        this.logger.info('uploading image', {
            fileName: file.name,
            fileSize: file.size,
            mimeType: file.type,
        })

        // validate file
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
            throw new Error('unsupported image format')
        }

        if (file.size > 10 * 1024 * 1024) {
            // 10mb
            throw new Error('file too large')
        }

        // read file buffer
        const buffer = Buffer.from(await file.arrayBuffer())

        // generate unique key
        const imageKey = `${nanoid()}-original.jpg`

        // save to minio
        const minioUrl = await this.storage.putObject(imageKey, buffer, file.type)

        // save to redis cache for quick access by worker
        const cacheKey = `ocr:image:${imageKey}`
        await this.cache.setBuffer(cacheKey, buffer, 3600) // 1 hour ttl

        // create image record
        const image = await this.imagesRepo.create({
            originalUrl: minioUrl,
            fileSize: file.size,
            mimeType: file.type,
            sourceService: metadata?.sourceService,
            sourceReference: metadata?.sourceReference,
        })

        // create recognition record
        const recognition = await this.recognitionsRepo.create({
            imageId: image.id,
            status: 'queued',
        })

        await this.queue.instance.add('recognition', {
            imageId: image.id,
            recognitionId: recognition.id,
            sourceService: metadata?.sourceService,
            sourceReference: metadata?.sourceReference,
            acceptedQrFormats: metadata?.acceptedQrFormats,
        })

        this.logger.info('image uploaded', {
            imageId: image.id,
            recognitionId: recognition.id,
        })

        return {
            imageId: image.id,
            recognitionId: recognition.id,
            status: 'queued',
        }
    }

    async getRecognitionStatus(recognitionId: string) {
        const recognition = await this.recognitionsRepo.findById(recognitionId)

        if (!recognition) {
            return null
        }

        return {
            recognitionId: recognition.id,
            imageId: recognition.imageId,
            status: recognition.status,
            resultType: recognition.resultType,
            text:
                recognition.resultType === 'text'
                    ? {
                        raw: recognition.rawText,
                        confidence: parseFloat(recognition.confidence || '0'),
                        engine: recognition.engine,
                        alignerUsed: recognition.alignerUsed,
                    }
                    : undefined,
            qr:
                recognition.resultType === 'qr'
                    ? {
                        data: recognition.qrData,
                        format: recognition.qrFormat,
                        location: recognition.qrLocation,
                    }
                    : undefined,
            processingTime: recognition.processingTime,
            error: recognition.error,
            completedAt: recognition.completedAt,
        }
    }

    async getImageUrl(
        imageId: string,
        type: 'original' | 'processed' = 'original',
        expiry: number = 3600
    ): Promise<string | null> {
        const image = await this.imagesRepo.findById(imageId)
        if (!image) return null

        const targetUrl = type === 'processed' ? image.processedUrl : image.originalUrl

        if (!targetUrl) {
            return null
        }

        const key = targetUrl.replace('minio://', '').split('/').slice(1).join('/')

        return await this.storage.getPresignedUrl(key, expiry)
    }
}
