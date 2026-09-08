import { getGameInfo } from "@/services/api";
import type { RoleInfo } from "@/types/game-info";

const TEAM_META: Record<string, { title: string; accent: string }> = {
  town: { title: "Town", accent: "text-emerald-400" },
  mafia: { title: "Mafia", accent: "text-rose-400" },
  neutral: { title: "Neutral", accent: "text-amber-400" },
};

export default async function RolesPage() {
  const { roles } = await getGameInfo();
  const teams = ["town", "mafia", "neutral"].filter((team) => roles.some((role) => role.team === team));

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-950 px-6 py-16 text-zinc-50">
      <main className="flex w-full max-w-3xl flex-col gap-10">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-3xl font-semibold tracking-tight">Roles</h1>
          <p className="max-w-xl text-zinc-400">
            Every role, in detail — what it does, when it acts, and a worked example of it in play.
          </p>
        </div>

        {teams.map((team) => (
          <TeamSection key={team} team={team} roles={roles.filter((role) => role.team === team)} />
        ))}
      </main>
    </div>
  );
}

function TeamSection({ team, roles }: { team: string; roles: RoleInfo[] }) {
  const meta = TEAM_META[team] ?? { title: team, accent: "text-zinc-400" };
  return (
    <div className="flex flex-col gap-4">
      <h2 className={`text-center text-sm font-semibold uppercase tracking-wide ${meta.accent}`}>{meta.title}</h2>
      <ul className="flex flex-col gap-4">
        {roles.map((role) => (
          <li key={role.key} className="rounded-xl border border-zinc-800 bg-zinc-900 px-5 py-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-medium text-zinc-100">{role.display_name}</span>
              <div className="flex flex-wrap gap-2 text-xs text-zinc-500">
                {role.acts_at_night && <span>Acts at night</span>}
                {role.hostile && <span className="text-rose-400">Hostile</span>}
                {role.max_uses !== null && <span>Max uses: {role.max_uses}</span>}
                {!role.allow_self_target && <span>No self-target</span>}
              </div>
            </div>
            <p className="mt-2 text-sm text-zinc-400">{role.description}</p>
            <p className="mt-2 text-sm text-zinc-500">
              <strong className="text-zinc-300">Example: </strong>
              {role.example}
            </p>
            {role.mutually_exclusive_with.length > 0 && (
              <p className="mt-2 text-xs text-zinc-500">
                Can&rsquo;t be enabled alongside:{" "}
                <span className="text-zinc-300">{role.mutually_exclusive_with.join(", ")}</span>
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
