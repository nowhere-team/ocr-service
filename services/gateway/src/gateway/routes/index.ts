import { Hono } from 'hono'

import { createHealthRoute } from './health'
import { createRecognitionRoutes } from './recognition'

export function registerRoutes() {
	return new Hono().route('/api/v1', createRecognitionRoutes()).route('/', createHealthRoute())
}
