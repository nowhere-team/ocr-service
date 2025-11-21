import { Hono } from 'hono'

export function createImageRoute() {
	return new Hono().get('/images/:id', async c => {
		const logger = c.get('logger')
		const services = c.get('services')

		const imageId = c.req.param('id')

		try {
			const url = await services.ocr.getImageUrl(imageId)

			if (!url) {
				return c.json({ error: 'image not found' }, 404)
			}

			return c.json({ imageId, url })
		} catch (error) {
			logger.error('failed to get image url', { error, imageId })
			return c.json({ error: (error as any).message }, 500)
		}
	})
}
