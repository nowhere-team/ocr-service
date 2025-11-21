import EventEmitter from 'events'
import type Redis from 'ioredis'

import type { Logger } from '@/platform/logger'

import type { EventMap } from './map.ts'

export interface EventBusConfig {
	subscriber: Redis
	publisher: Redis
}

export class EventBus extends EventEmitter {
	private subscriber: Redis
	private publisher: Redis
	private logger: Logger

	constructor(config: EventBusConfig, logger: Logger) {
		super()
		this.setMaxListeners(0)
		this.subscriber = config.subscriber
		this.publisher = config.publisher
		this.logger = logger.named('event-bus')

		this.subscriber.on('message', this.handleMessage.bind(this))
	}

	async publish<K extends keyof EventMap>(channel: string, eventName: K, data: EventMap[K]) {
		const message = JSON.stringify({
			event: eventName,
			timestamp: Date.now(),
			...data,
		})

		await this.publisher.publish(channel, message)
		this.logger.debug('event published', { channel, event: eventName })
	}

	private handleMessage(_channel: string, message: string) {
		try {
			const data = JSON.parse(message)
			const eventName = data.event

			if (!eventName) {
				this.logger.warn('received message without event field')
				return
			}

			this.emit(eventName, data)
		} catch (error) {
			this.logger.error('failed to parse redis message', { error })
		}
	}

	override on<K extends keyof EventMap>(event: K, listener: (data: EventMap[K]) => void): this {
		return super.on(event, listener)
	}

	async close() {
		this.removeAllListeners()
		this.logger.info('event bus closed')
	}
}
