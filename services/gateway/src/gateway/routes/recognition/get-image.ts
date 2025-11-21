import { Hono } from 'hono'

export function createImageRoute() {
    return new Hono().get('/images/:id', async c => {
        const logger = c.get('logger')
        const services = c.get('services')

        const imageId = c.req.param('id')
        const imageType = c.req.query('type') || 'original' // original | processed

        if (imageType !== 'original' && imageType !== 'processed') {
            return c.json({ error: 'type must be "original" or "processed"' }, 400)
        }

        try {
            const url = await services.ocr.getImageUrl(imageId, imageType)

            if (!url) {
                return c.json({
                    error: imageType === 'processed'
                        ? 'processed image not found or not yet available'
                        : 'image not found'
                }, 404)
            }

            return c.json({ imageId, type: imageType, url })
        } catch (error) {
            logger.error('failed to get image url', { error, imageId, imageType })
            return c.json({ error: (error as any).message }, 500)
        }
    })
}