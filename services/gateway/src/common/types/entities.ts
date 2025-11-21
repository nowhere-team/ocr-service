import * as schema from '@/platform/database/schema'

// database entities
export type Image = typeof schema.images.$inferSelect
export type RecognitionResult = typeof schema.recognitionResults.$inferSelect
