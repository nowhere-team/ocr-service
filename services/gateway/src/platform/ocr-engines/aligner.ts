import ky, { type KyInstance } from 'ky'

import type { Logger } from '@/platform/logger'

export type AlignmentMode = 'classic' | 'neural'

export interface AlignerConfig {
    url: string
    timeout: number
}

export interface AlignerOptions {
    mode?: AlignmentMode
    aggressive?: boolean
    applyOcrPrep?: boolean
    simplifyPercent?: number
    debugMode?: boolean
    recognitionId?: string
    imageId?: string
}

export interface AlignmentResult {
    warped: Buffer
    preprocessed: Buffer
}

export class AlignerClient {
    private readonly api: KyInstance

    constructor(
        private readonly logger: Logger,
        private readonly config: AlignerConfig,
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
                        this.logger.debug('aligner request starting', {
                            url: request.url,
                        })
                    },
                ],
                beforeError: [
                    error => {
                        const { request, response } = error
                        this.logger.error('aligner request failed', {
                            url: request.url,
                            status: response?.status,
                            statusText: response?.statusText,
                        })
                        return error
                    },
                ],
                afterResponse: [
                    (_request, _options, response) => {
                        this.logger.debug('aligner response received', {
                            status: response.status,
                        })
                    },
                ],
            },
        })
    }

    async align(buffer: Buffer, options?: AlignerOptions): Promise<AlignmentResult> {
        const startTime = Date.now()

        try {
            const formData = new FormData()
            formData.append('image', new Blob([buffer]))

            const searchParams = new URLSearchParams()

            const mode = options?.mode ?? 'classic'
            searchParams.set('mode', mode)

            if (options?.aggressive !== undefined) {
                searchParams.set('aggressive', String(options.aggressive))
            }
            if (options?.applyOcrPrep !== undefined) {
                searchParams.set('apply_ocr_prep', String(options.applyOcrPrep))
            }
            if (options?.simplifyPercent !== undefined) {
                searchParams.set('simplify_percent', String(options.simplifyPercent))
            }
            if (options?.debugMode !== undefined) {
                searchParams.set('debug_mode', String(options.debugMode))
            }
            if (options?.recognitionId) {
                searchParams.set('recognition_id', options.recognitionId)
            }
            if (options?.imageId) {
                searchParams.set('image_id', options.imageId)
            }

            const response = await this.api.post('api/v1/align', {
                body: formData,
                searchParams,
            }).json<{warped: string, preprocessed: string}>()

            const warpedBuffer = Buffer.from(response.warped, 'base64')
            const preprocessedBuffer = Buffer.from(response.preprocessed, 'base64')

            const duration = Date.now() - startTime

            this.logger.info('image alignment completed', {
                originalSize: buffer.length,
                warpedSize: warpedBuffer.length,
                preprocessedSize: preprocessedBuffer.length,
                mode,
                aggressive: options?.aggressive ?? false,
                applyOcrPrep: options?.applyOcrPrep ?? false,
                debugMode: options?.debugMode ?? false,
                duration,
            })

            return {
                warped: warpedBuffer,
                preprocessed: preprocessedBuffer,
            }
        } catch (error) {
            const duration = Date.now() - startTime

            this.logger.error('image alignment failed', {
                error,
                duration,
            })

            throw new Error(`aligner service unavailable: ${error instanceof Error ? error.message : 'unknown error'}`)
        }
    }
}