// Mirrors app/games/mafia/roles.py and role_assignment.py on the backend.
// Villager and Mafia are always in the game and aren't toggleable; every
// other role is optional and chosen per-game by the host via
// `enabled_role_keys`.

export type Team = "town" | "mafia" | "neutral";

export interface RoleInfo {
  key: string;
  display_name: string;
  team: Team;
  description: string;
}

export const ROLE_CATALOG: RoleInfo[] = [
  {
    key: "villager",
    display_name: "Villager",
    team: "town",
    description: "No special ability. Use the day's discussion and your vote to find the mafia.",
  },
  {
    key: "mafia",
    display_name: "Mafia",
    team: "mafia",
    description: "Each night, choose a player alongside the rest of the mafia to eliminate.",
  },
  {
    key: "detective",
    display_name: "Detective",
    team: "town",
    description: "Each night, investigate one player to learn which team they're on.",
  },
  {
    key: "doctor",
    display_name: "Doctor",
    team: "town",
    description: "Each night, choose one player to protect from elimination.",
  },
  {
    key: "bodyguard",
    display_name: "Bodyguard",
    team: "town",
    description:
      "Each night, choose one player to guard. If the mafia targets your guarded player, you die defending them instead.",
  },
  {
    key: "vigilante",
    display_name: "Vigilante",
    team: "town",
    description:
      "Each night, you may kill one player. You only have 2 shots for the whole game — use them wisely.",
  },
  {
    key: "escort",
    display_name: "Escort",
    team: "town",
    description: "Each night, choose one player to distract — blocking whatever night action they attempt.",
  },
  {
    key: "godfather",
    display_name: "Godfather",
    team: "mafia",
    description:
      "Leads the mafia's nightly kill just like any mafia member, but appears innocent to a detective's investigation.",
  },
  {
    key: "mayor",
    display_name: "Mayor",
    team: "town",
    description:
      "Has no night action. May publicly reveal at any time during the day to permanently double the weight of their vote.",
  },
  {
    key: "jester",
    display_name: "Jester",
    team: "neutral",
    description: "Wins alone if the town votes to lynch you. A night kill doesn't count.",
  },
  {
    key: "serial_killer",
    display_name: "Serial Killer",
    team: "neutral",
    description:
      "Each night, kill a player independent of the mafia. Wins alone by being the last one standing.",
  },
  {
    key: "survivor",
    display_name: "Survivor",
    team: "neutral",
    description: "Has no night action. Wins personally simply by surviving to the end of the game, alive.",
  },
  {
    key: "terrorist",
    display_name: "Terrorist",
    team: "mafia",
    description:
      "Each night, plant a bomb on a player. It doesn't go off that night — it detonates during the following night's resolution unless you withdraw it first. Counts toward the mafia's win, but doesn't know who the mafia are and never sees their picks.",
  },
  {
    key: "traitor",
    display_name: "Traitor",
    team: "neutral",
    description:
      "Has no night action and looks like an ordinary villager, even to a detective's investigation. Secretly wins alongside the mafia.",
  },
];

// Villager and Mafia are always in the roster and can't be turned off.
export const TOGGLEABLE_ROLE_KEYS: string[] = ROLE_CATALOG.filter(
  (role) => role.key !== "villager" && role.key !== "mafia"
).map((role) => role.key);

// Mirrors DEFAULT_ENABLED_ROLE_KEYS in role_assignment.py.
export const DEFAULT_ENABLED_ROLE_KEYS: string[] = ["detective", "doctor"];

// Mirrors clamp_mafia_count in role_assignment.py.
export function clampMafiaCount(playerCount: number, requested: number | null): number {
  if (requested === null) {
    return Math.max(1, Math.floor(playerCount / 4));
  }
  const maxMafia = Math.max(1, Math.min(Math.floor(playerCount / 3), playerCount - 2));
  return Math.max(1, Math.min(requested, maxMafia));
}

// Mirrors build_composition's overflow check in role_assignment.py: mafia
// count contributes one slot each, plus one slot per other enabled role.
export function totalRoleSlots(mafiaCount: number, enabledRoleKeys: string[]): number {
  const specialCount = enabledRoleKeys.filter((key) => key !== "godfather").length;
  return mafiaCount + specialCount;
}
