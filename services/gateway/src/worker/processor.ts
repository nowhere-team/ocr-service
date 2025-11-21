import { type Job, Worker } from 'bullmq'

import type { EventBus } from '@/platform/events'
import type { Logger } from '@/platform/logger'
import type { Queue, RecognitionJob } from '@/platform/queue'
import type { Services } from '@/services'

export async function createWorker(
	queue: Queue,
	eventBus: EventBus,
	services: Services,
	logger: Logger,
	concurrency: number,
): Promise<Worker> {
	const worker = new Worker<RecognitionJob>(
		'ocr-jobs',
		async (job: Job<RecognitionJob>) => {
			const startTime = Date.now()

			logger.info('processing job', {
				jobId: job.id,
				imageId: job.data.imageId,
				recognitionId: job.data.recognitionId,
			})

			// publish processing event
			await eventBus.publish('ocr:events', 'ocr.processing', {
				imageId: job.data.imageId,
				recognitionId: job.data.recognitionId,
				sourceService: job.data.sourceService,
				sourceReference: job.data.sourceReference,
			})

			try {
				// process recognition
				const result = await services.processor.process(job.data.imageId, job.data.recognitionId)

				const processingTime = Date.now() - startTime

				// publish completed event
				await eventBus.publish('ocr:events', 'ocr.completed', {
					imageId: job.data.imageId,
					recognitionId: job.data.recognitionId,
					sourceService: job.data.sourceService,
					sourceReference: job.data.sourceReference,
					resultType: result.resultType,
					text: result.text,
					qr: result.qr,
					processingTime,
				})

				logger.info('job completed', {
					jobId: job.id,
					recognitionId: job.data.recognitionId,
					resultType: result.resultType,
					processingTime,
				})

				return result
			} catch (error) {
				logger.error('job failed', {
					jobId: job.id,
					recognitionId: job.data.recognitionId,
					error,
				})

				// publish failed event
				await eventBus.publish('ocr:events', 'ocr.failed', {
					imageId: job.data.imageId,
					recognitionId: job.data.recognitionId,
					sourceService: job.data.sourceService,
					sourceReference: job.data.sourceReference,
					error: (error as any).message,
				})

				throw error
			}
		},
		{
			connection: await queue.client,
			concurrency,
			limiter: {
				max: 10,
				duration: 1000,
			},
		},
	)

	worker.on('completed', job => {
		logger.info('worker job completed', {
			jobId: job.id,
			duration: job.finishedOn! - job.processedOn!,
		})
	})

	worker.on('failed', (job, error) => {
		logger.error('worker job failed', {
			jobId: job?.id,
			error,
		})
	})

	worker.on('error', error => {
		logger.error('worker error', { error })
	})

	return worker
}
