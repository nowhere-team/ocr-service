import { Hono } from 'hono'

import { createImageRoute } from './get-image.ts'
import { createStatusRoute } from './get-status.ts'
import { createRecognizeRoute } from './recognize.ts'

export function createRecognitionRoutes() {
	return new Hono().route('/', createRecognizeRoute()).route('/', createImageRoute()).route('/', createStatusRoute())
}
