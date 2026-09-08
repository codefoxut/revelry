import { getGameInfo } from "@/services/api";

export default async function TieBreakersPage() {
  const { tie_breakers: tieBreakers } = await getGameInfo();

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-950 px-6 py-16 text-zinc-50">
      <main className="flex w-full max-w-3xl flex-col gap-10">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-3xl font-semibold tracking-tight">Tie-Breakers</h1>
          <p className="max-w-xl text-zinc-400">
            The host picks how these situations resolve before starting the game.
          </p>
        </div>

        {tieBreakers.map((tieBreaker) => (
          <div key={tieBreaker.key} className="flex flex-col gap-4">
            <div className="flex flex-col items-center gap-1 text-center">
              <h2 className="text-2xl font-semibold tracking-tight">{tieBreaker.title}</h2>
              <p className="max-w-xl text-zinc-400">{tieBreaker.description}</p>
            </div>
            <ul className="flex flex-col gap-4">
              {tieBreaker.options.map((option) => (
                <li key={option.key} className="rounded-xl border border-zinc-800 bg-zinc-900 px-5 py-4">
                  <span className="font-medium text-zinc-100">{option.label}</span>
                  <p className="mt-2 text-sm text-zinc-400">{option.description}</p>
                  <p className="mt-2 text-sm text-zinc-500">
                    <strong className="text-zinc-300">Example: </strong>
                    {option.example}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </main>
    </div>
  );
}
