import { Hono } from 'hono'

export function createHealthRoute() {
	return new Hono().get('/health', c => {
		return c.json({
			status: 'ok',
			service: 'ocr-gateway',
			timestamp: new Date().toISOString(),
		})
	})
}
