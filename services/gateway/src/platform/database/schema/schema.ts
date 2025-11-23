import { relations } from 'drizzle-orm'
import { boolean, integer, jsonb, numeric, pgEnum, pgTable, text, uuid, varchar } from 'drizzle-orm/pg-core'

import { timestamptz } from './utils'

export const resultTypeEnum = pgEnum('result_type_enum', ['text', 'qr'])
export const statusEnum = pgEnum('status_enum', ['queued', 'processing', 'completed', 'failed'])
export const engineEnum = pgEnum('engine_enum', ['tesseract', 'paddleocr'])
export const qrFormatEnum = pgEnum('qr_format_enum', ['fiscal', 'url', 'unknown'])

export const images = pgTable('images', {
	id: uuid('id').primaryKey().defaultRandom(),

	// where stored
	originalUrl: varchar('original_url', { length: 512 }).notNull(),
	processedUrl: varchar('processed_url', { length: 512 }),

	// metadata
	fileSize: integer('file_size').notNull(),
	mimeType: varchar('mime_Type', { length: 50 }).notNull(),
	width: integer('width'),
	height: integer('height'),

	// source
	sourceService: varchar('source_service', { length: 50 }),
	sourceReference: varchar('source_reference', { length: 128 }),

	uploadedAt: timestamptz('uploaded_at').notNull().defaultNow(),
})

export const recognitionResults = pgTable('recognition_results', {
    id: uuid('id').primaryKey().defaultRandom(),
    imageId: uuid('image_id')
        .notNull()
        .references(() => images.id, { onDelete: 'cascade' }),

    status: statusEnum('status').notNull().default('queued'),
    resultType: resultTypeEnum('result_type'),

    rawText: text('raw_text'),
    confidence: numeric('confidence', { mode: 'number', precision: 3, scale: 2 }),
    engine: engineEnum('engine'),
    aligned: boolean('aligned').default(false),
    usedPreprocessed: boolean('used_preprocessed').default(false),

    qrData: text('qr_data'),
    qrFormat: qrFormatEnum('qr_format'),
    qrLocation: jsonb('qr_location').$type<{ x: number; y: number; width: number; height: number }>(),
    foundInPreprocessed: boolean('found_in_preprocessed').default(false),

    processingTime: integer('processing_time'),
    queueWaitTime: integer('queue_wait_time'),
    attemptNumber: integer('attempt_number').notNull().default(1),
    error: text('error'),

    createdAt: timestamptz('created_at').notNull().defaultNow(),
    completedAt: timestamptz('completed_at'),
})

export const imagesRelations = relations(images, ({ many }) => ({
	recognitionResults: many(recognitionResults),
}))

export const recognitionResultsRelations = relations(recognitionResults, ({ one }) => ({
	image: one(images, {
		fields: [recognitionResults.imageId],
		references: [images.id],
	}),
}))
