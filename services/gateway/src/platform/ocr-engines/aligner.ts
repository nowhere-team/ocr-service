import ky, { type KyInstance } from 'ky'

import type { Logger } from '@/platform/logger'

export interface AlignerConfig {
    url: string
    timeout: number
}

export interface AlignerOptions {
    aggressive?: boolean
    applyOcrPrep?: boolean
    simplifyStep?: number
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

    async align(buffer: Buffer, options?: AlignerOptions): Promise<Buffer> {
        const startTime = Date.now()

        try {
            const formData = new FormData()
            formData.append('image', new Blob([buffer]))

            const searchParams = new URLSearchParams()
            if (options?.aggressive !== undefined) {
                searchParams.set('aggressive', String(options.aggressive))
            }
            if (options?.applyOcrPrep !== undefined) {
                searchParams.set('apply_ocr_prep', String(options.applyOcrPrep))
            }
            if (options?.simplifyStep !== undefined) {
                searchParams.set('simplify_step', String(options.simplifyStep))
            }

            const response = await this.api.post('api/v1/align', {
                body: formData,
                searchParams,
            })

            const alignedBuffer = Buffer.from(await response.arrayBuffer())

            const duration = Date.now() - startTime

            this.logger.info('image alignment completed', {
                originalSize: buffer.length,
                alignedSize: alignedBuffer.length,
                aggressive: options?.aggressive ?? false,
                applyOcrPrep: options?.applyOcrPrep ?? false,
                duration,
            })

            return alignedBuffer
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