export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-zinc-950 px-6 py-24 text-zinc-50">
      <main className="flex w-full max-w-2xl flex-col items-center gap-8 text-center">
        <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-1 text-sm font-medium text-zinc-400">
          Revelry
        </span>

        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Mafia, with your friends,{" "}
          <span className="text-rose-500">in your browser.</span>
        </h1>

        <p className="max-w-md text-lg leading-8 text-zinc-400">
          No installs, no accounts. Grab a room code, split into town and
          mafia, and see who survives the night.
        </p>

        <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
          <button
            type="button"
            disabled
            className="h-12 w-full rounded-full bg-rose-500 px-8 font-medium text-white opacity-60 transition-colors sm:w-auto"
          >
            Create Room
          </button>
          <button
            type="button"
            disabled
            className="h-12 w-full rounded-full border border-zinc-700 px-8 font-medium text-zinc-200 opacity-60 transition-colors sm:w-auto"
          >
            Join with Code
          </button>
        </div>

        <p className="text-sm text-zinc-600">
          Room creation is coming soon — lobby and gameplay are next up.
        </p>
      </main>
    </div>
  );
}
