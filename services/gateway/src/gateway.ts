import { startGateway, stopGateway } from '@/bootstrap/gateway'

const app = await startGateway()

const SHUTDOWN_SIGNALS = ['SIGTERM', 'SIGINT', 'SIGKILL'] as const

for (const signal of SHUTDOWN_SIGNALS) {
	process.on(signal, async () => {
		try {
			await stopGateway(app)
			process.exit(0)
		} catch {
			process.exit(1)
		}
	})
}
