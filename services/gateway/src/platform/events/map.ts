export interface EventMap {
	'ocr.queued': {
		imageId: string
		recognitionId: string
		sourceService?: string
		sourceReference?: string
		position: number
		estimatedWait: number
	}
	'ocr.processing': {
		imageId: string
		recognitionId: string
		sourceService?: string
		sourceReference?: string
	}
	'ocr.completed': {
		imageId: string
		recognitionId: string
		sourceService?: string
		sourceReference?: string
		resultType: 'text' | 'qr'
		text?: {
			raw: string
			confidence: number
			engine: 'tesseract' | 'paddleocr'
			aligned: boolean
		}
		qr?: {
			data: string
			format: 'fiscal' | 'url' | 'unknown'
			location?: { x: number; y: number; width: number; height: number }
		}
		processingTime: number
	},
    'ocr.debug.step': {
        recognitionId: string
        imageId: string
        step: string
        stepNumber: number
        imageKey: string
        description: string
        metadata?: Record<string, any>
    },
	'ocr.failed': {
		imageId: string
		recognitionId: string
		sourceService?: string
		sourceReference?: string
		error: string
	},
    'aligner.debug.step': {
        recognitionId: string
        imageId: string
        step: string
        stepNumber: number
        imageKey: string
        description: string
        metadata?: Record<string, any>
    }
}
