"""Long-form player-facing reference content: worked examples per role, phase
write-ups, tie-breaker option copy, general rules, and FAQ entries.

Deliberately kept separate from `roles.py` (rather than adding fields to
`Role`) so the core gameplay dataclass — touched by every role/engine test —
never needs to change just because a sentence of explainer copy changes.
This module is pure data, read by `services/game_info_presenter.py` and
served read-only via `GET /api/game-info`; nothing here affects gameplay.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseContent:
    key: str
    name: str
    summary: str
    details: str
    example: str


@dataclass(frozen=True)
class TieBreakerOption:
    key: str
    label: str
    description: str
    example: str


@dataclass(frozen=True)
class TieBreakerContent:
    key: str
    title: str
    description: str
    options: tuple[TieBreakerOption, ...]


@dataclass(frozen=True)
class RuleSection:
    title: str
    body: str
    example: str | None = None


@dataclass(frozen=True)
class FaqEntry:
    question: str
    answer: str


ROLE_EXAMPLES: dict[str, str] = {
    "villager": (
        "You have no night action, so during the day you listen to how people vote and defend "
        "themselves, then vote for whoever you suspect is mafia."
    ),
    "mafia": (
        "You and your fellow mafia both submit \"eliminate Priya\" and lock it in — Priya is "
        "eliminated when night resolves. If your teammate instead locks in a different target, "
        "the mafia hasn't reached consensus and the host's conflict-resolution setting decides "
        "what happens instead."
    ),
    "oracle": (
        "You investigate a player who turns out to be the Serial Killer. Since Oracle only "
        "reports mafia-aligned or not, you're told \"not mafia\" — a Detective would have said "
        "\"neutral\" instead."
    ),
    "detective": (
        "You investigate a player who turns out to be the Serial Killer and are told \"neutral\" "
        "— the exact team, not just a mafia/not-mafia read. If you investigate the Godfather "
        "instead, you're told \"town\", since the Godfather appears innocent to investigation."
    ),
    "doctor": (
        "You protect Sam. That same night, the mafia targets Sam. Sam survives — the protection "
        "cancels the kill, and no one else needs to know it happened."
    ),
    "bodyguard": (
        "You guard Sam. The mafia targets Sam that night — you die in Sam's place instead, and "
        "Sam survives. If the mafia had targeted someone else, nothing happens to you or Sam."
    ),
    "vigilante": (
        "On night 2 you shoot a player you're confident is mafia — correctly, and they're "
        "eliminated. You have one shot left for the rest of the game, so you hold it unless "
        "you're just as sure again."
    ),
    "escort": (
        "You distract the Detective on a night they planned to investigate someone. Their "
        "investigation never happens — no result, as if they'd taken no action at all."
    ),
    "hypnotizer": (
        "Mechanically identical to the Escort: you hypnotize the Doctor on the same night the "
        "mafia attacks their protected target. The Doctor's protection never goes out, so the "
        "mafia's kill goes through."
    ),
    "godfather": (
        "The Detective investigates you. Despite leading the mafia's kill, you're reported as "
        "\"town\" — the same masking the Traitor gets, so investigation alone can't unmask you."
    ),
    "mayor": (
        "Round 3, the vote is close. You publicly reveal as Mayor — from that point on, every "
        "vote you cast counts as two, for the rest of the game, in every remaining round."
    ),
    "jester": (
        "The town, certain you're mafia, votes to eliminate you. You're voted out — and you win "
        "immediately, alone, regardless of how the rest of the game would have gone. If the "
        "mafia kills you at night instead, none of that happens — only an elimination by day "
        "vote counts."
    ),
    "serial_killer": (
        "Every night you pick your own target, entirely independent of the mafia's kill. You "
        "keep killing until either you're voted out/found, or you're the only player left alive "
        "— at which point you win alone."
    ),
    "survivor": (
        "You take no night action and mostly stay quiet during the day. The game ends with the "
        "mafia defeated and you still alive — you personally win too, regardless of which team "
        "\"the town\" was rooting for."
    ),
    "terrorist": (
        "Night 1 you plant your bomb on a player. It doesn't detonate that night. Night 2 "
        "arrives — if you haven't withdrawn it, it goes off during that night's resolution, "
        "eliminating them, even though you never saw who the actual mafia team is."
    ),
    "traitor": (
        "The Detective investigates you, expecting to find mafia. You're reported as \"town\" — "
        "you look exactly like an ordinary Villager to any investigation, even though the mafia "
        "winning also means you win."
    ),
}

PHASES: tuple[PhaseContent, ...] = (
    PhaseContent(
        key="night",
        name="Night",
        summary="Players with a night action secretly choose a target.",
        details=(
            "Every role that acts at night — the mafia, Detective/Oracle, Doctor, Bodyguard, "
            "Vigilante, Escort/Hypnotizer, Serial Killer, Terrorist, and so on — privately "
            "submits a target. The mafia team sees each other's live picks and must lock in a "
            "matching target together; everyone else's action is private even from other "
            "players on their own team. Once every acting player has submitted (and the mafia "
            "have locked in, or the host advances anyway), the night resolves: protections "
            "cancel kills, blocks cancel whatever they blocked, and the results are revealed."
        ),
        example=(
            "The mafia lock in \"eliminate Priya\". The Doctor, not knowing that, protects Sam "
            "instead. Night resolves: Priya is eliminated, unless a Bodyguard was guarding her, "
            "in which case the Bodyguard dies defending her and Priya survives instead."
        ),
    ),
    PhaseContent(
        key="day",
        name="Day",
        summary="The town discusses who they suspect, out loud.",
        details=(
            "Whoever was eliminated overnight is revealed. Surviving players openly discuss "
            "who they suspect and why — there's no secret ballot yet, this is just "
            "conversation. A revealed Mayor can choose to reveal during this phase, doubling "
            "their vote weight for every remaining vote in the game."
        ),
        example=(
            "The night's elimination is announced. Two players accuse each other of being "
            "mafia based on how they voted the previous round; everyone else weighs in before "
            "voting opens."
        ),
    ),
    PhaseContent(
        key="voting",
        name="Voting",
        summary="Everyone votes, in the open, for who to eliminate.",
        details=(
            "Votes are cast publicly and can change right up until the host advances the phase "
            "— there's no hidden ballot or locking mechanic on the day side, unlike the mafia's "
            "night-time consensus. Whoever has the most votes (a revealed Mayor's vote counts "
            "double) is eliminated when voting resolves. If two or more players are tied for "
            "the most votes, the host's day-tie-resolution setting decides what happens."
        ),
        example=(
            "6 living players vote: 3 for Alex, 2 for Priya, 1 for Sam. Alex has the plurality "
            "and is eliminated when the vote resolves."
        ),
    ),
    PhaseContent(
        key="elimination",
        name="Elimination",
        summary="The vote's result is applied and revealed.",
        details=(
            "The player chosen by the vote (or by the tie-breaker, if there was a tie) is "
            "eliminated and their role is revealed to everyone. If eliminating them ends the "
            "game — every mafia member gone, every town member gone, a Jester correctly voted "
            "out, or a lone hostile neutral left standing — the game ends here instead of "
            "returning to Night."
        ),
        example=(
            "Alex is eliminated and revealed as the Godfather. With no mafia-team players left "
            "alive, the game ends immediately in a town win — there's no next Night phase."
        ),
    ),
)

TIE_BREAKERS: tuple[TieBreakerContent, ...] = (
    TieBreakerContent(
        key="conflict_resolution",
        title="If the mafia can't agree",
        description=(
            "Chosen by the host before the game starts. Decides what happens when night "
            "resolves and the living mafia-team players haven't all locked in the same target "
            "— whether because they disagree, or because not everyone locked in at all."
        ),
        options=(
            TieBreakerOption(
                key="kill_any",
                label="Kill someone at random",
                description=(
                    "A random living player dies instead — mafia included. This raises the "
                    "stakes of not coordinating: staying silent or disagreeing doesn't "
                    "guarantee safety."
                ),
                example=(
                    "Two mafia players lock in different targets and the third never locks in "
                    "at all. Night resolves with no consensus, so one random living player — "
                    "possibly even a mafia member — is eliminated instead."
                ),
            ),
            TieBreakerOption(
                key="no_kill",
                label="No one dies",
                description=(
                    "A gentler fallback: if the mafia can't agree, the night simply passes with "
                    "no elimination at all, the same as if they'd chosen not to kill."
                ),
                example=(
                    "The mafia's live picks never converge on a single target by the time the "
                    "host advances the phase. Night resolves with no elimination — everyone "
                    "who was alive is still alive going into Day."
                ),
            ),
        ),
    ),
    TieBreakerContent(
        key="day_tie_resolution",
        title="If the day vote ties",
        description=(
            "Chosen by the host before the game starts. Decides what happens when two or more "
            "players are tied for the most votes once voting resolves."
        ),
        options=(
            TieBreakerOption(
                key="no_elimination",
                label="No one is eliminated",
                description=(
                    "A tie means the town failed to agree — no one is voted out this round, "
                    "and the game moves straight to Night."
                ),
                example=(
                    "Alex and Priya are tied at 3 votes each, with no one else close. Voting "
                    "resolves with no elimination, and the game proceeds to Night."
                ),
            ),
            TieBreakerOption(
                key="random_among_tied",
                label="Randomly pick one of the tied",
                description=(
                    "One of the tied players is eliminated at random — a tie still costs the "
                    "town a player, it just doesn't get to choose which one."
                ),
                example=(
                    "Alex and Priya are tied at 3 votes each. One of the two is chosen at "
                    "random and eliminated; the other survives to the next round."
                ),
            ),
        ),
    ),
)

RULES_SECTIONS: tuple[RuleSection, ...] = (
    RuleSection(
        title="Objective",
        body=(
            "Every role belongs to one of three teams. Town wins by eliminating every mafia "
            "member. Mafia wins by reaching parity with (or outnumbering) the town. Neutral "
            "roles mostly don't care who wins the main fight — some (like Jester and Survivor) "
            "have their own personal win condition instead, and a hostile neutral (Serial "
            "Killer) is actively trying to be the only one left standing."
        ),
    ),
    RuleSection(
        title="Round structure",
        body=(
            "Every round cycles through the same four phases in order: Night, Day, Voting, "
            "Elimination. After Elimination, either the game is over, or it loops back to a "
            "new Night. See the Gameplay page for a detailed walkthrough of each phase."
        ),
    ),
    RuleSection(
        title="Win conditions",
        body=(
            "The game checks for a winner after every elimination, whether from a night kill or "
            "a day vote. Town wins the moment no mafia-team player is left alive. Mafia wins the "
            "moment mafia-team players are at least as numerous as town-team players. A living "
            "hostile neutral (Serial Killer) blocks both of those outcomes until they're "
            "eliminated — the game keeps going even at mafia/town parity while they're alive — "
            "and if they're ever the sole survivor, they win alone instead. The Jester has its "
            "own condition layered on top: being voted out by the town (not killed at night) is "
            "an instant, personal win regardless of every other team's state. Survivor and "
            "Traitor track their own personal win alongside whichever team result actually "
            "happens (Survivor: alive at the end; Traitor: alongside a mafia win)."
        ),
        example=(
            "6 players are alive: 2 mafia, 4 town. The mafia eliminate one town player at "
            "night, bringing it to 2 mafia vs. 3 town — not yet a mafia win. The next night "
            "they eliminate another, making it 2 mafia vs. 2 town: mafia are now at parity, "
            "and the game ends in a mafia win."
        ),
    ),
    RuleSection(
        title="Role composition",
        body=(
            "The host chooses which optional roles are active and how many mafia-team slots "
            "exist before starting the game — Villager and Mafia are always available as the "
            "\"everyone else\" fallback. A handful of role pairs are mutually exclusive because "
            "they'd otherwise conflict mechanically (see the Roles page for exactly which "
            "pairs, and why) — the lobby greys out a role's chip the moment its exclusive "
            "partner is enabled, and the server independently rejects starting a game with both "
            "enabled at once even if a client tried to bypass the UI."
        ),
    ),
    RuleSection(
        title="Self-targeting",
        body=(
            "Most night-acting roles may target themselves (e.g. a Doctor can protect "
            "themselves). A few can't, because it wouldn't make sense or would trivialize the "
            "role: the mafia, Detective, Oracle, Vigilante, Escort, Hypnotizer, Godfather, "
            "Serial Killer, and Terrorist can never target themselves."
        ),
    ),
)

FAQ: tuple[FaqEntry, ...] = (
    FaqEntry(
        question="What's the minimum number of players?",
        answer=(
            "4. At 4 players the room defaults to exactly one mafia and one villager slot "
            "plus whichever special roles the host enables, up to however many player slots "
            "exist."
        ),
    ),
    FaqEntry(
        question="What happens if the mafia can't agree on a target?",
        answer=(
            "The host picks the fallback before the game starts: either a random living player "
            "dies anyway (mafia included), or no one dies that night. See the Tie-Breakers page "
            "for the full breakdown."
        ),
    ),
    FaqEntry(
        question="What happens if the day vote ties?",
        answer=(
            "Same idea as the mafia's tie-breaker, but for voting: the host chooses in advance "
            "whether a tie means no one is eliminated, or one of the tied players is chosen at "
            "random."
        ),
    ),
    FaqEntry(
        question="Can the Jester win even after being eliminated?",
        answer=(
            "Yes — the Jester's win condition is being voted out by the town during the day. "
            "It's an instant personal win the moment that happens, regardless of what would "
            "have happened to any other team. Being killed at night doesn't trigger it."
        ),
    ),
    FaqEntry(
        question="Why is the Oracle/Detective (or Escort/Hypnotizer) chip greyed out in the lobby?",
        answer=(
            "Those pairs are mutually exclusive — a game can only ever have one of each pair "
            "active, since they either share the exact same underlying mechanic (Escort/"
            "Hypnotizer) or would create two competing investigator roles (Detective/Oracle). "
            "Enabling one automatically disables the other, on both the lobby UI and the "
            "server."
        ),
    ),
    FaqEntry(
        question="Can I target myself with my night action?",
        answer=(
            "Depends on the role. Doctor, Bodyguard, Mayor-style no-action roles, and most "
            "others allow it. The mafia, Detective, Oracle, Vigilante, Escort, Hypnotizer, "
            "Godfather, Serial Killer, and Terrorist cannot target themselves."
        ),
    ),
    FaqEntry(
        question="Does the Detective see through the Godfather or Traitor?",
        answer=(
            "No. Both the Godfather (mafia team) and Traitor (neutral team) are reported as "
            "\"town\" to any investigation — Detective or Oracle — even though the Godfather "
            "leads the mafia's kill and the Traitor secretly wins alongside the mafia."
        ),
    ),
    FaqEntry(
        question="What does a revealed Mayor's vote actually do?",
        answer=(
            "A Mayor has no night action at all. At any point during the day, they may publicly "
            "reveal — from then on, every vote they cast (for the rest of the game) counts as "
            "two votes instead of one, when the plurality is tallied."
        ),
    ),
    FaqEntry(
        question="What happens if I disconnect mid-game?",
        answer=(
            "During the lobby (before the game starts), a disconnected player has a 30-second "
            "grace period before they're dropped from the room. Once the game is underway, a "
            "disconnect just waits for you to reconnect with the same player identity — you "
            "won't be removed from an in-progress game."
        ),
    ),
    FaqEntry(
        question="Can a Neutral role win even if it isn't Town or Mafia that wins?",
        answer=(
            "Yes, for the roles designed that way. Jester wins by being voted out. Survivor "
            "wins personally just by being alive at the end, regardless of which main team "
            "won. Traitor wins alongside a mafia win specifically. Serial Killer, as a hostile "
            "neutral, blocks both Town and Mafia from winning while alive, and wins alone if "
            "left as the sole survivor."
        ),
    ),
)
