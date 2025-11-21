import { Hono } from 'hono'

// POST /api/v1/recognize
export function createRecognizeRoute() {
	return new Hono().post('/recognize', async c => {
		const logger = c.get('logger')
		const services = c.get('services')

		try {
			const formData = await c.req.formData()
			const image = formData.get('image') as File
			const sourceService = formData.get('sourceService') as string | undefined
			const sourceReference = formData.get('sourceReference') as string | undefined

			if (!image) {
				return c.json({ error: 'image is required' }, 400)
			}

			const result = await services.ocr.uploadImage(image, {
				sourceService,
				sourceReference,
			})

			logger.info('recognition queued', {
				imageId: result.imageId,
				recognitionId: result.recognitionId,
				sourceService,
				sourceReference,
			})

			return c.json(result, 202)
		} catch (error) {
			logger.error('failed to upload image', { error })
			return c.json({ error: (error as any).message }, 500)
		}
	})
}
