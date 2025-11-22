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
			const acceptedQrFormatsRaw = formData.get('acceptedQrFormats') as string | undefined

			if (!image) {
				return c.json({ error: 'image is required' }, 400)
			}

			let acceptedQrFormats: Array<'fiscal' | 'url' | 'unknown'> | undefined
			if (acceptedQrFormatsRaw) {
				const formats = acceptedQrFormatsRaw
					.split(',')
					.map(f => f.trim())
					.filter(f => f.length > 0)

				const validFormats = ['fiscal', 'url', 'unknown']
				const invalidFormats = formats.filter(f => !validFormats.includes(f))

				if (invalidFormats.length > 0) {
					return c.json(
						{
							error: `invalid formats: ${invalidFormats.join(', ')}. allowed: fiscal, url, unknown`,
						},
						400,
					)
				}

				acceptedQrFormats = formats as Array<'fiscal' | 'url' | 'unknown'>
			}

			const result = await services.ocr.uploadImage(image, {
				sourceService,
				sourceReference,
				acceptedQrFormats,
			})

			logger.info('recognition queued', {
				imageId: result.imageId,
				recognitionId: result.recognitionId,
				sourceService,
				sourceReference,
				acceptedQrFormats,
			})

			return c.json(result, 202)
		} catch (error) {
			logger.error('failed to upload image', { error })
			return c.json({ error: (error as any).message }, 500)
		}
	})
}
