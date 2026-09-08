import { getGameInfo } from "@/services/api";

export default async function FaqPage() {
  const { faq } = await getGameInfo();

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-950 px-6 py-16 text-zinc-50">
      <main className="flex w-full max-w-3xl flex-col gap-10">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-3xl font-semibold tracking-tight">FAQ</h1>
          <p className="max-w-xl text-zinc-400">Common questions about how Mafia plays out.</p>
        </div>

        <ul className="flex flex-col gap-3">
          {faq.map((entry) => (
            <li key={entry.question} className="rounded-xl border border-zinc-800 bg-zinc-900 px-5 py-3">
              <details>
                <summary className="cursor-pointer font-medium text-zinc-100 marker:text-rose-400">
                  {entry.question}
                </summary>
                <p className="mt-2 text-sm text-zinc-400">{entry.answer}</p>
              </details>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
