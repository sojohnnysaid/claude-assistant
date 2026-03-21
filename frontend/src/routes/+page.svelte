<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	interface Machine {
		name: string;
		connected_at: number;
		last_heartbeat: number;
		has_active_session: boolean;
	}

	interface Session {
		session_id: string;
		machine_name: string;
		ngrok_url: string | null;
		started_at: number;
		status: string;
	}

	let machines = $state<Machine[]>([]);
	let session = $state<Session | null>(null);
	let loading = $state(false);
	let error = $state('');
	let ws: WebSocket | null = null;

	function connectWs() {
		const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
		ws = new WebSocket(`${proto}//${location.host}/ws/ui`);

		ws.onmessage = (e) => {
			const data = JSON.parse(e.data);

			if (data.type === 'initial_state') {
				machines = data.machines;
				session = data.session;
			} else if (data.type === 'machine_online') {
				if (!machines.find((m) => m.name === data.machine)) {
					machines = [
						...machines,
						{
							name: data.machine,
							connected_at: Date.now() / 1000,
							last_heartbeat: Date.now() / 1000,
							has_active_session: false
						}
					];
				}
			} else if (data.type === 'machine_offline') {
				machines = machines.filter((m) => m.name !== data.machine);
			} else if (data.type === 'session_starting') {
				session = {
					session_id: data.session_id,
					machine_name: data.machine,
					ngrok_url: null,
					started_at: Date.now() / 1000,
					status: 'starting'
				};
				loading = false;
			} else if (data.type === 'session_active') {
				if (session) {
					session = { ...session, ngrok_url: data.ngrok_url, status: 'active' };
				}
			} else if (data.type === 'session_stopped') {
				session = null;
				loading = false;
			} else if (data.type === 'session_error') {
				session = null;
				loading = false;
				error = data.error;
				setTimeout(() => (error = ''), 5000);
			}
		};

		ws.onclose = () => {
			setTimeout(connectWs, 3000);
		};
	}

	async function startSession(machineName: string) {
		loading = true;
		error = '';
		try {
			const res = await fetch('/api/sessions', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ machine: machineName })
			});
			if (!res.ok) {
				const data = await res.json();
				throw new Error(data.detail || 'Failed to start session');
			}
		} catch (e: any) {
			error = e.message;
			loading = false;
		}
	}

	async function endSession() {
		loading = true;
		error = '';
		try {
			const res = await fetch('/api/sessions', { method: 'DELETE' });
			if (!res.ok) {
				const data = await res.json();
				throw new Error(data.detail || 'Failed to end session');
			}
		} catch (e: any) {
			error = e.message;
			loading = false;
		}
	}

	function formatDuration(startedAt: number): string {
		const seconds = Math.floor(Date.now() / 1000 - startedAt);
		const h = Math.floor(seconds / 3600);
		const m = Math.floor((seconds % 3600) / 60);
		if (h > 0) return `${h}h ${m}m`;
		return `${m}m`;
	}

	let durationInterval: ReturnType<typeof setInterval>;

	onMount(() => {
		connectWs();
		durationInterval = setInterval(() => {
			// Force reactivity for duration display
			if (session) session = { ...session };
		}, 30000);
	});

	onDestroy(() => {
		ws?.close();
		clearInterval(durationInterval);
	});
</script>

<div class="flex min-h-screen items-center justify-center bg-gray-950 p-4">
	<div class="w-full max-w-md">
		<!-- Header -->
		<div class="mb-8 text-center">
			<h1 class="text-3xl font-bold text-white">
				Claude Assistant
				{#if session?.status === 'active'}
					<span class="ml-2 inline-block h-3 w-3 animate-pulse rounded-full bg-red-500"></span>
				{/if}
			</h1>
			<p class="mt-1 text-sm text-gray-500">Voice Agent Control</p>
		</div>

		<!-- Error -->
		{#if error}
			<div class="mb-4 rounded-lg border border-red-800 bg-red-950 p-3 text-sm text-red-300">
				{error}
			</div>
		{/if}

		<!-- Active Session -->
		{#if session}
			<div class="rounded-xl border border-gray-800 bg-gray-900 p-6">
				<div class="mb-4 flex items-center justify-between">
					<span class="text-sm font-medium text-gray-400">Active Session</span>
					<span
						class="rounded-full px-2 py-0.5 text-xs font-medium
						{session.status === 'active'
							? 'bg-green-900 text-green-300'
							: 'bg-yellow-900 text-yellow-300'}"
					>
						{session.status}
					</span>
				</div>

				<div class="space-y-3">
					<div>
						<span class="text-xs text-gray-500">Machine</span>
						<p class="text-lg font-medium text-white">{session.machine_name}</p>
					</div>
					<div>
						<span class="text-xs text-gray-500">Duration</span>
						<p class="text-lg font-medium text-white">{formatDuration(session.started_at)}</p>
					</div>
				</div>

				<button
					onclick={endSession}
					disabled={loading}
					class="mt-6 w-full cursor-pointer rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
				>
					{loading ? 'Ending...' : 'End Session'}
				</button>
			</div>

		<!-- No Session — Machine List -->
		{:else}
			<div class="rounded-xl border border-gray-800 bg-gray-900 p-6">
				<h2 class="mb-4 text-sm font-medium text-gray-400">Online Machines</h2>

				{#if machines.length === 0}
					<p class="py-8 text-center text-sm text-gray-600">No machines online</p>
				{:else}
					<div class="space-y-2">
						{#each machines as machine}
							<div
								class="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-950 px-4 py-3"
							>
								<div class="flex items-center gap-3">
									<span class="h-2.5 w-2.5 rounded-full bg-green-500"></span>
									<span class="text-sm font-medium text-white">{machine.name}</span>
								</div>
								<button
									onclick={() => startSession(machine.name)}
									disabled={loading}
									class="cursor-pointer rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
								>
									{loading ? 'Starting...' : 'Start'}
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>
