import { startWorker, stopWorker } from '@/bootstrap/worker'

const app = await startWorker()

const SHUTDOWN_SIGNALS = ['SIGTERM', 'SIGINT', 'SIGKILL'] as const

for (const signal of SHUTDOWN_SIGNALS) {
	process.on(signal, async () => {
		try {
			await stopWorker(app)
			process.exit(0)
		} catch {
			process.exit(1)
		}
	})
}
