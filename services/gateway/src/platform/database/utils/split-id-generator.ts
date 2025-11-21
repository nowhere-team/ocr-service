import { eq } from 'drizzle-orm'
import { customAlphabet } from 'nanoid'

import { schema, type Tx } from '@/platform/database'

const alphabet = '23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz'
const nanoid = customAlphabet(alphabet, 8)

/**
 * generates a unique shortId for the splits table
 * works inside a drizzle transaction
 */
export async function generateSplitId(tx: Tx): Promise<string> {
	const maxAttempts = 5

	for (let attempt = 0; attempt < maxAttempts; attempt++) {
		const id = nanoid()

		const exists = await tx.query.splits.findFirst({
			where: eq(schema.splits.shortId, id),
		})

		if (!exists) {
			return id
		}
	}

	throw new Error('failed to generate unique shortId after several attempts')
}
