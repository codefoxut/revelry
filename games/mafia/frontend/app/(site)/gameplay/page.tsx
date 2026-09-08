import { getGameInfo } from "@/services/api";

export default async function GameplayPage() {
  const { phases } = await getGameInfo();

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-950 px-6 py-16 text-zinc-50">
      <main className="flex w-full max-w-3xl flex-col gap-10">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-3xl font-semibold tracking-tight">Gameplay</h1>
          <p className="max-w-xl text-zinc-400">
            Each round cycles through four phases, in order. The game repeats these until one
            team&rsquo;s win condition is met.
          </p>
        </div>

        <ol className="flex flex-col gap-4">
          {phases.map((phase, index) => (
            <li key={phase.key} className="rounded-xl border border-zinc-800 bg-zinc-900 px-5 py-4">
              <div className="flex items-baseline gap-3">
                <span className="text-sm font-semibold text-rose-400">{index + 1}</span>
                <span className="font-medium text-zinc-100">{phase.name}</span>
              </div>
              <p className="mt-2 text-sm text-zinc-400">{phase.summary}</p>
              <p className="mt-2 text-sm text-zinc-400">{phase.details}</p>
              <p className="mt-2 text-sm text-zinc-500">
                <strong className="text-zinc-300">Example: </strong>
                {phase.example}
              </p>
            </li>
          ))}
        </ol>
      </main>
    </div>
  );
}
