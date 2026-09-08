import { getGameInfo } from "@/services/api";

export default async function RulesPage() {
  const { rules } = await getGameInfo();

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-950 px-6 py-16 text-zinc-50">
      <main className="flex w-full max-w-3xl flex-col gap-10">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-3xl font-semibold tracking-tight">Rules</h1>
          <p className="max-w-xl text-zinc-400">The full rundown of how a game of Mafia is won and played.</p>
        </div>

        <ul className="flex flex-col gap-4">
          {rules.map((section) => (
            <li key={section.title} className="rounded-xl border border-zinc-800 bg-zinc-900 px-5 py-4">
              <h2 className="font-medium text-zinc-100">{section.title}</h2>
              <p className="mt-2 text-sm text-zinc-400">{section.body}</p>
              {section.example && (
                <p className="mt-2 text-sm text-zinc-500">
                  <strong className="text-zinc-300">Example: </strong>
                  {section.example}
                </p>
              )}
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
