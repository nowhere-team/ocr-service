import { Hono } from 'hono'

export function createStatusRoute() {
	return new Hono().get('/recognitions/:id', async c => {
		const logger = c.get('logger')
		const services = c.get('services')

		const recognitionId = c.req.param('id')

		try {
			const result = await services.ocr.getRecognitionStatus(recognitionId)

			if (!result) {
				return c.json({ error: 'recognition not found' }, 404)
			}

			return c.json(result)
		} catch (error) {
			logger.error('failed to get recognition status', { error, recognitionId })
			return c.json({ error: (error as any).message }, 500)
		}
	})
}
