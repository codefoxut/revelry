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
    key: "oracle",
    display_name: "Oracle",
    team: "town",
    description:
      "Each night, investigate one player to learn if they're mafia-aligned or not — a simpler, binary read than the detective's three-way team report.",
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
    key: "hypnotizer",
    display_name: "Hypnotizer",
    team: "town",
    description: "Each night, choose one player to hypnotize — blocking whatever night action they attempt.",
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

// player_count -> { min, max, default } mafia count, curated for good
// gameplay across the room's 4-20 player range. Mirrors MAFIA_COUNT_TABLE in
// backend/app/games/mafia/role_assignment.py -- both sides must agree so the
// lobby's dropdown bounds always match what the server will accept.
export const MAFIA_COUNT_TABLE: Record<number, { min: number; max: number; default: number }> = {
  4: { min: 1, max: 1, default: 1 },
  5: { min: 1, max: 1, default: 1 },
  6: { min: 1, max: 2, default: 1 },
  7: { min: 1, max: 2, default: 1 },
  8: { min: 1, max: 2, default: 2 },
  9: { min: 1, max: 3, default: 2 },
  10: { min: 1, max: 3, default: 2 },
  11: { min: 1, max: 3, default: 2 },
  12: { min: 1, max: 4, default: 3 },
  13: { min: 1, max: 4, default: 3 },
  14: { min: 1, max: 4, default: 3 },
  15: { min: 1, max: 5, default: 3 },
  16: { min: 1, max: 5, default: 4 },
  17: { min: 1, max: 5, default: 4 },
  18: { min: 1, max: 6, default: 4 },
  19: { min: 1, max: 6, default: 4 },
  20: { min: 1, max: 6, default: 5 },
};

// Mirrors mafia_count_bounds in role_assignment.py.
export function mafiaCountBounds(playerCount: number): { min: number; max: number; default: number } {
  return MAFIA_COUNT_TABLE[Math.min(Math.max(playerCount, 4), 20)];
}

// Mirrors clamp_mafia_count in role_assignment.py.
export function clampMafiaCount(playerCount: number, requested: number | null): number {
  const { min, max, default: defaultCount } = mafiaCountBounds(playerCount);
  if (requested === null) {
    return defaultCount;
  }
  return Math.max(min, Math.min(requested, max));
}

// Mirrors build_composition's overflow check in role_assignment.py: mafia
// count contributes one slot each, plus one slot per other enabled role.
export function totalRoleSlots(mafiaCount: number, enabledRoleKeys: string[]): number {
  const specialCount = enabledRoleKeys.filter((key) => key !== "godfather").length;
  return mafiaCount + specialCount;
}

// Role pairs that can never both be enabled at once. Mirrors
// _MUTUALLY_EXCLUSIVE_ROLE_PAIRS in role_assignment.py.
const MUTUALLY_EXCLUSIVE_ROLE_PAIRS: [string, string][] = [
  ["detective", "oracle"],
  ["escort", "hypnotizer"],
];

// Whether `roleKey` could be turned on (in addition to whatever's already
// enabled) without breaking the game for this player/mafia count. Used to
// grey out lobby role chips that wouldn't fit rather than letting the host
// discover the problem only after hitting Start.
export function isRoleAvailable(
  roleKey: string,
  playerCount: number,
  mafiaCount: number,
  enabledRoleKeys: string[],
): boolean {
  const withRole = enabledRoleKeys.includes(roleKey) ? enabledRoleKeys : [...enabledRoleKeys, roleKey];
  if (totalRoleSlots(mafiaCount, withRole) > playerCount) return false;

  for (const [a, b] of MUTUALLY_EXCLUSIVE_ROLE_PAIRS) {
    if (roleKey === a && enabledRoleKeys.includes(b)) return false;
    if (roleKey === b && enabledRoleKeys.includes(a)) return false;
  }

  if (roleKey === "terrorist") {
    // Mirrors _check_win's mafia_alive >= town_alive parity rule in
    // engine.py: a living Terrorist counts toward mafia_alive, so it needs
    // enough town players left over that adding it doesn't create instant
    // win-parity before anyone has even acted.
    const mafiaAlive = mafiaCount + 1;
    const townSpecialCount = enabledRoleKeys.filter(
      (key) => key !== "terrorist" && ROLE_CATALOG.find((role) => role.key === key)?.team === "town",
    ).length;
    const townAlive = playerCount - mafiaCount - 1 - townSpecialCount;
    if (townAlive <= mafiaAlive) return false;
  }

  return true;
}
