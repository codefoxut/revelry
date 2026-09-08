"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useRoomStore } from "@/store/roomStore";
import { avatarEmoji } from "@/lib/avatars";
import type { Player } from "@/types/room";
import { LOCATION_CATALOG, locationDisplayName } from "@/lib/locations";

export function GameView() {
  const router = useRouter();
  const room = useRoomStore((state) => state.room);
  const selfPlayerId = useRoomStore((state) => state.selfPlayerId);
  const myRole = useRoomStore((state) => state.myRole);
  const votes = useRoomStore((state) => state.votes);
  const discussionTimer = useRoomStore((state) => state.discussionTimer);
  const gameOver = useRoomStore((state) => state.gameOver);
  const lastError = useRoomStore((state) => state.lastError);
  const sendCommand = useRoomStore((state) => state.sendCommand);

  const phase = room?.game_state?.phase;
  const roundNumber = room?.game_state?.round_number;

  if (!room || !room.game_state) return null;

  const self = room.players.find((player) => player.id === selfPlayerId);
  const isHost = self?.is_host ?? false;
  const activePlayers = room.players.filter((player) => !player.is_spectator);

  function submitVote(targetId: string) {
    sendCommand({ type: "cast_vote", target_player_id: targetId });
  }

  function guessLocation(locationKey: string) {
    sendCommand({ type: "guess_location", location_key: locationKey });
  }

  function advancePhase() {
    sendCommand({ type: "advance_phase" });
  }

  if (gameOver) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-6 bg-zinc-950 px-6 py-24 text-zinc-50">
        <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-1 text-sm font-medium text-zinc-400">
          Game over
        </span>
        <h1 className="text-3xl font-semibold tracking-tight">
          {gameOver.winningSide === "spies" ? "The spy wins" : "Everyone else wins"}
        </h1>
        <p className="text-center text-sm text-zinc-400">
          The location was <span className="font-medium text-rose-400">{gameOver.location}</span>.
        </p>
        <p className="text-center text-sm text-zinc-400">
          {gameOver.accusedPlayerId
            ? `${playerName(room.players, gameOver.accusedPlayerId)} was accused.`
            : "No one was accused."}
        </p>

        <div className="flex w-full max-w-sm flex-col gap-2 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
          <span className="text-center text-xs uppercase tracking-wide text-zinc-500">
            Final roles
          </span>
          <ul className="flex flex-col gap-1">
            {gameOver.reveals.map((reveal) => (
              <li
                key={reveal.player_id}
                className="flex items-center justify-between text-sm text-zinc-300"
              >
                <span>
                  {playerName(room.players, reveal.player_id)}
                  {reveal.player_id === selfPlayerId ? " (you)" : ""}
                </span>
                <span className={reveal.is_spy ? "font-medium text-rose-400" : "text-zinc-400"}>
                  {reveal.is_spy ? "Spy" : reveal.role}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <button
          type="button"
          onClick={() => router.push("/")}
          className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400"
        >
          Back home
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {myRole && (
        <div className="flex flex-col items-center gap-1 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
          <span className="text-xs uppercase tracking-wide text-zinc-500">Your role</span>
          {self && <span aria-hidden="true" className="text-2xl">{avatarEmoji(self.avatar)}</span>}
          {myRole.isSpy ? (
            <>
              <span className="text-xl font-semibold text-rose-400">You are the SPY</span>
              <p className="mt-1 text-center text-sm text-zinc-400">
                Figure out the location without getting caught — or guess it outright to win instantly.
              </p>
            </>
          ) : (
            <>
              <span className="text-xl font-semibold text-rose-400">{myRole.location}</span>
              <span className="text-xs uppercase tracking-wide text-zinc-600">{myRole.role}</span>
              <p className="mt-1 text-center text-sm text-zinc-400">
                Ask questions and answer carefully — one of you is the spy.
              </p>
            </>
          )}
        </div>
      )}

      <div className="flex flex-col items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
        <span className="rounded-full border border-rose-900 bg-rose-950/50 px-4 py-1 text-sm font-medium capitalize text-rose-300">
          {phase} &middot; Round {roundNumber}
        </span>

        {phase === "discussion" && discussionTimer && (
          <DiscussionCountdown deadlineAt={discussionTimer.deadlineAt} />
        )}

        {lastError && (
          <p role="alert" className="text-center text-sm text-rose-400">
            {lastError.message}
          </p>
        )}

        {(phase === "discussion" || phase === "voting") && myRole?.isSpy && (
          // Guessing the location only ever succeeds for the spy (the
          // backend rejects it otherwise with invalid_game_state), so the
          // control is gated client-side to the spy for a cleaner UX rather
          // than shown to everyone and relying on the error message.
          <LocationGuessControl onGuess={guessLocation} />
        )}

        {phase === "voting" && (
          <VotePanel
            key={`voting-${roundNumber}`}
            players={activePlayers}
            selfPlayerId={selfPlayerId}
            votes={votes}
            onSelect={submitVote}
          />
        )}

        {isHost && phase === "discussion" && (
          <button
            type="button"
            onClick={advancePhase}
            className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400"
          >
            Advance to voting
          </button>
        )}
        {isHost && phase === "voting" && (
          <button
            type="button"
            onClick={advancePhase}
            className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400"
          >
            Resolve vote
          </button>
        )}
      </div>
    </div>
  );
}

function VotePanel({
  players,
  selfPlayerId,
  votes,
  onSelect,
}: {
  players: Player[];
  selfPlayerId: string | null;
  votes: Record<string, string>;
  onSelect: (targetId: string) => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const voteCounts = countVotes(votes);

  function handleSelect(targetId: string) {
    setSelectedId(targetId);
    onSelect(targetId);
  }

  return (
    <div className="flex w-full flex-col gap-2">
      <span className="text-center text-xs uppercase tracking-wide text-zinc-500">
        Vote for who you think the spy is
      </span>
      <ul className="flex flex-col gap-1">
        {players.map((player) => (
          <li key={player.id}>
            <button
              type="button"
              onClick={() => handleSelect(player.id)}
              className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm transition-colors ${
                selectedId === player.id
                  ? "border-rose-500 bg-rose-950/50 text-rose-200"
                  : "border-zinc-800 text-zinc-300 hover:border-zinc-600"
              }`}
            >
              <span>
                {player.display_name}
                {player.id === selfPlayerId ? " (you)" : ""}
              </span>
              {voteCounts[player.id] ? (
                <span className="text-xs text-zinc-500">{voteCounts[player.id]} vote(s)</span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LocationGuessControl({ onGuess }: { onGuess: (locationKey: string) => void }) {
  const [open, setOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  function handleGuess(key: string) {
    setSelectedKey(key);
    onGuess(key);
    setOpen(false);
  }

  return (
    <div className="flex w-full flex-col gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="h-10 rounded-full border border-rose-500 px-6 font-medium text-rose-400 transition-colors hover:bg-rose-950/50"
      >
        {open ? "Cancel" : "Guess the location"}
      </button>
      {selectedKey && !open && (
        <p className="text-center text-sm text-zinc-500">
          Last guess: <span className="text-zinc-300">{locationDisplayName(selectedKey)}</span>
        </p>
      )}
      {open && (
        <div className="grid max-h-64 grid-cols-2 gap-1 overflow-y-auto sm:grid-cols-3">
          {LOCATION_CATALOG.map((location) => (
            <button
              key={location.key}
              type="button"
              onClick={() => handleGuess(location.key)}
              className="rounded-lg border border-zinc-800 px-2 py-1.5 text-left text-sm text-zinc-300 transition-colors hover:border-zinc-600"
            >
              {location.displayName}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function DiscussionCountdown({ deadlineAt }: { deadlineAt: number }) {
  const [remainingMs, setRemainingMs] = useState(() => Math.max(0, deadlineAt - Date.now()));

  useEffect(() => {
    setRemainingMs(Math.max(0, deadlineAt - Date.now()));
    const interval = setInterval(() => {
      setRemainingMs(Math.max(0, deadlineAt - Date.now()));
    }, 250);
    return () => clearInterval(interval);
  }, [deadlineAt]);

  const secondsLeft = Math.ceil(remainingMs / 1000);
  const minutes = Math.floor(secondsLeft / 60);
  const seconds = secondsLeft % 60;

  return (
    <p className="text-center text-sm text-zinc-500">
      Discussion ends in{" "}
      <span className="font-medium text-rose-400">
        {minutes}:{seconds.toString().padStart(2, "0")}
      </span>
      {" "}— the server will advance automatically.
    </p>
  );
}

function countVotes(votes: Record<string, string>): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const target of Object.values(votes)) {
    counts[target] = (counts[target] ?? 0) + 1;
  }
  return counts;
}

function playerName(players: Player[], playerId: string): string {
  return players.find((player) => player.id === playerId)?.display_name ?? "Someone";
}
