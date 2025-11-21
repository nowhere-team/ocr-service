import { Client as MinioClient } from 'minio'

import type { Logger } from '@/platform/logger'

export interface Storage {
	putObject(key: string, data: Buffer, contentType?: string): Promise<string>
	getObject(key: string): Promise<Buffer>
	deleteObject(key: string): Promise<void>
	getPresignedUrl(key: string, expiry?: number): Promise<string>
}

export interface StorageConfig {
	endpoint: string
	port: number
	accessKey: string
	secretKey: string
	useSSL: boolean
	bucket: string
}

class MinioStorage implements Storage {
	private client: MinioClient
	private readonly bucket: string

	constructor(
		private config: StorageConfig,
		private logger: Logger,
	) {
		this.client = new MinioClient({
			endPoint: config.endpoint,
			port: config.port,
			accessKey: config.accessKey,
			secretKey: config.secretKey,
			useSSL: config.useSSL,
		})
		this.bucket = config.bucket
	}

	async ensureBucket() {
		const exists = await this.client.bucketExists(this.bucket)
		if (!exists) {
			await this.client.makeBucket(this.bucket)
			this.logger.info('bucket created', { bucket: this.bucket })
		}
	}

	async putObject(key: string, data: Buffer, contentType?: string): Promise<string> {
		const metadata = contentType ? { 'Content-Type': contentType } : undefined

		await this.client.putObject(this.bucket, key, data, data.length, metadata)

		this.logger.debug('object stored', {
			bucket: this.bucket,
			key,
			size: data.length,
		})

		return `minio://${this.bucket}/${key}`
	}

	async getObject(key: string): Promise<Buffer> {
		const stream = await this.client.getObject(this.bucket, key)

		const chunks: Buffer[] = []
		for await (const chunk of stream) {
			chunks.push(chunk)
		}

		const buffer = Buffer.concat(chunks)

		this.logger.debug('object retrieved', {
			bucket: this.bucket,
			key,
			size: buffer.length,
		})

		return buffer
	}

	async deleteObject(key: string): Promise<void> {
		await this.client.removeObject(this.bucket, key)

		this.logger.debug('object deleted', {
			bucket: this.bucket,
			key,
		})
	}

	async getPresignedUrl(key: string, expiry: number = 3600): Promise<string> {
		return await this.client.presignedGetObject(this.bucket, key, expiry)
	}
}

export async function createStorage(logger: Logger, config: StorageConfig): Promise<Storage> {
	const storage = new MinioStorage(config, logger.named('storage'))
	await storage.ensureBucket()
	logger.info('storage initialized', {
		endpoint: config.endpoint,
		bucket: config.bucket,
	})
	return storage
}
