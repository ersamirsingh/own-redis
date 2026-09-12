export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8 text-center">
      <div className="max-w-2xl space-y-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-red-500/30 bg-red-950/40 px-3 py-1 text-xs font-semibold text-red-400">
          <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
          AI-Native In-Memory Data Platform
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
          Welcome to <span className="text-red-500">PyRedis</span>
        </h1>
        <p className="text-neutral-400 text-lg">
          High-performance distributed in-memory data engine with operational Data Console, real-time tracing, and autonomous Google Gemini diagnostics.
        </p>
        <div className="flex justify-center gap-4 pt-4">
          <a
            href="/dashboard"
            className="rounded-lg bg-red-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-red-500 transition-colors"
          >
            Launch Console
          </a>
          <a
            href="/login"
            className="rounded-lg border border-neutral-700 bg-neutral-900 px-5 py-2.5 text-sm font-semibold text-neutral-300 hover:bg-neutral-800 transition-colors"
          >
            Sign In
          </a>
        </div>
      </div>
    </main>
  );
}
