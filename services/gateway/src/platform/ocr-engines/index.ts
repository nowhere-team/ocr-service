import type { Logger } from '@/platform/logger'

import { AlignerClient } from './aligner'
import { PaddleOCRClient } from './paddleocr'
import { TesseractClient } from './tesseract'

export * from './aligner'
export * from './paddleocr'
export * from './tesseract'

export interface OCREnginesConfig {
	tesseractUrl: string
	paddleocrUrl: string
	alignerUrl: string
	timeout: number
}

export interface OCREngines {
	tesseract: TesseractClient
	paddleocr: PaddleOCRClient
	aligner: AlignerClient
}

export function createOCREngines(logger: Logger, config: OCREnginesConfig): OCREngines {
	const tesseract = new TesseractClient(logger.named('ocr-engine/tesseract'), {
		url: config.tesseractUrl,
		timeout: config.timeout,
	})

	const paddleocr = new PaddleOCRClient(logger.named('ocr-engine/paddleocr'), {
		url: config.paddleocrUrl,
		timeout: config.timeout,
	})

	const aligner = new AlignerClient(logger.named('ocr-engine/aligner'), {
		url: config.alignerUrl,
		timeout: config.timeout,
	})

	logger.info('ocr engines initialized', {
		tesseract: config.tesseractUrl,
		paddleocr: config.paddleocrUrl,
		aligner: config.alignerUrl,
	})

	return { tesseract, paddleocr, aligner }
}
