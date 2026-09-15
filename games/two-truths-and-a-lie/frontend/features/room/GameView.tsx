"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRoomStore } from "@/store/roomStore";
import { clearPlayerId } from "@/lib/session";
import { avatarEmoji } from "@/lib/avatars";
import type { Player, GameState } from "@/types/room";
import type { ClientCommand } from "@/types/ws-events";

function playerName(players: Player[], playerId: string | null): string {
  if (!playerId) return "";
  return players.find((p) => p.id === playerId)?.display_name ?? "Unknown";
}

function Leaderboard({ players, scores }: { players: Player[]; scores: Record<string, number> }) {
  const ranked = [...players]
    .filter((p) => p.id in scores)
    .sort((a, b) => (scores[b.id] ?? 0) - (scores[a.id] ?? 0));

  return (
    <ol className="flex flex-col gap-2">
      {ranked.map((player, index) => (
        <li
          key={player.id}
          className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-2"
        >
          <div className="flex items-center gap-2">
            <span className="w-5 text-sm text-zinc-500">{index + 1}</span>
            <span aria-hidden="true">{avatarEmoji(player.avatar)}</span>
            <span className="font-medium">{player.display_name}</span>
          </div>
          <span className="font-mono text-lg text-rose-400">{scores[player.id] ?? 0}</span>
        </li>
      ))}
    </ol>
  );
}

function GameOverScreen({
  players,
  scores,
  selfPlayerId,
  onLeave,
}: {
  players: Player[];
  scores: Record<string, number>;
  selfPlayerId: string | null;
  onLeave: () => void;
}) {
  const sorted = [...players]
    .filter((p) => p.id in scores)
    .sort((a, b) => (scores[b.id] ?? 0) - (scores[a.id] ?? 0));
  const winner = sorted[0] ?? null;
  const topScore = winner ? scores[winner.id] : 0;
  const isTie = sorted.filter((p) => scores[p.id] === topScore).length > 1;

  return (
    <div className="flex flex-col items-center gap-6 text-center">
      <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-1 text-sm font-medium text-zinc-400">
        Game over
      </span>
      <h2 className="text-2xl font-semibold tracking-tight">
        {isTie ? (
          "It's a tie!"
        ) : winner ? (
          <>
            <span className="text-rose-500">{winner.display_name}</span> wins!
          </>
        ) : null}
      </h2>
      {winner?.id === selfPlayerId && !isTie && (
        <p className="text-zinc-400">You fooled them all. Well played.</p>
      )}
      <Leaderboard players={players} scores={scores} />
      <button
        type="button"
        onClick={onLeave}
        className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400"
      >
        Back home
      </button>
    </div>
  );
}

function SubmittingView({
  selfPlayerId,
  gameState,
  players,
  sendCommand,
}: {
  selfPlayerId: string | null;
  gameState: GameState;
  players: Player[];
  sendCommand: (cmd: ClientCommand) => void;
}) {
  const isStoryteller = gameState.storyteller_id === selfPlayerId;
  const storytellerName = playerName(players, gameState.storyteller_id);
  const [statements, setStatements] = useState(["", "", ""]);
  const [lieIndex, setLieIndex] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleChange(index: number, value: string) {
    setStatements((prev) => prev.map((s, i) => (i === index ? value : s)));
  }

  function handleSubmit() {
    if (lieIndex === null) {
      setError("Pick which statement is the lie.");
      return;
    }
    if (statements.some((s) => !s.trim())) {
      setError("All three statements must be filled in.");
      return;
    }
    setError(null);
    setSubmitting(true);
    sendCommand({
      type: "submit_statements",
      statements: statements.map((s) => s.trim()),
      lie_index: lieIndex,
    });
  }

  if (!isStoryteller) {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <p className="text-lg font-medium">
          <span className="text-rose-400">{storytellerName}</span> is writing their statements…
        </p>
        <p className="text-sm text-zinc-500">Sit tight while they craft their lies.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-center text-sm text-zinc-400">
        You&rsquo;re the Storyteller this round. Write two true statements and one lie, then mark
        which one is the lie.
      </p>
      {statements.map((s, i) => (
        <div key={i} className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setLieIndex(i)}
            aria-label={`Mark statement ${i + 1} as the lie`}
            className={`h-8 w-8 shrink-0 rounded-full border text-sm font-medium transition-colors ${
              lieIndex === i
                ? "border-rose-500 bg-rose-500 text-white"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
            }`}
          >
            {i + 1}
          </button>
          <input
            value={s}
            onChange={(e) => handleChange(i, e.target.value)}
            placeholder={`Statement ${i + 1}`}
            maxLength={200}
            className="h-12 flex-1 rounded-xl border border-zinc-700 bg-zinc-900 px-4 text-zinc-50 outline-none focus:border-rose-500"
          />
        </div>
      ))}
      {lieIndex !== null && (
        <p className="text-center text-xs text-zinc-500">
          Statement {lieIndex + 1} is marked as the lie.
        </p>
      )}
      {error && (
        <p role="alert" className="text-center text-sm text-rose-400">
          {error}
        </p>
      )}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={submitting}
        className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? "Submitting…" : "Submit"}
      </button>
    </div>
  );
}

function VotingView({
  selfPlayerId,
  gameState,
  players,
  sendCommand,
}: {
  selfPlayerId: string | null;
  gameState: GameState;
  players: Player[];
  sendCommand: (cmd: ClientCommand) => void;
}) {
  const isStoryteller = gameState.storyteller_id === selfPlayerId;
  const storytellerName = playerName(players, gameState.storyteller_id);
  const totalVoters = players.filter((p) => !p.is_spectator).length - 1;
  const [voted, setVoted] = useState(false);

  function castVote(index: number) {
    if (voted || isStoryteller) return;
    setVoted(true);
    sendCommand({ type: "cast_vote", choice_index: index });
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-center text-sm text-zinc-400">
        <span className="text-rose-400">{storytellerName}</span>&rsquo;s statements — which one is
        the lie?
      </p>

      <div className="flex flex-col gap-3">
        {(gameState.statements ?? []).map((statement, i) => (
          <button
            key={i}
            type="button"
            onClick={() => castVote(i)}
            disabled={isStoryteller || voted}
            className={`rounded-xl border px-4 py-4 text-left text-sm transition-colors ${
              isStoryteller || voted
                ? "cursor-default border-zinc-800 bg-zinc-900 text-zinc-400"
                : "border-zinc-700 bg-zinc-900 text-zinc-50 hover:border-rose-500 hover:bg-zinc-800"
            }`}
          >
            <span className="mr-3 font-mono text-zinc-500">{i + 1}.</span>
            {statement}
          </button>
        ))}
      </div>

      {isStoryteller && (
        <p className="text-center text-sm text-zinc-500">
          Storytellers can&rsquo;t vote. Waiting for everyone else…
        </p>
      )}
      {voted && !isStoryteller && (
        <p className="text-center text-sm text-zinc-500">Vote cast! Waiting for others…</p>
      )}

      <p className="text-center text-sm text-zinc-600">
        {gameState.voted_count} / {totalVoters} voted
      </p>
    </div>
  );
}

function RevealView({
  selfPlayerId,
  gameState,
  players,
  revealData,
  sendCommand,
  isHost,
}: {
  selfPlayerId: string | null;
  gameState: GameState;
  players: Player[];
  revealData: { lieIndex: number; correctVoters: string[]; scoresDelta: Record<string, number> } | null;
  sendCommand: (cmd: ClientCommand) => void;
  isHost: boolean;
}) {
  const isStoryteller = gameState.storyteller_id === selfPlayerId;
  const storytellerName = playerName(players, gameState.storyteller_id);
  const lieIndex = revealData?.lieIndex ?? gameState.lie_index;
  const correctVoters = revealData?.correctVoters ?? gameState.correct_voters ?? [];
  const isLast = gameState.round_number >= gameState.total_rounds;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-center text-sm text-zinc-400">
        The lie was statement{" "}
        <span className="font-bold text-rose-400">{lieIndex !== null ? lieIndex + 1 : "?"}</span>
        {" "}— written by <span className="text-rose-400">{storytellerName}</span>.
      </p>

      <div className="flex flex-col gap-3">
        {(gameState.statements ?? []).map((statement, i) => {
          const isLie = i === lieIndex;
          return (
            <div
              key={i}
              className={`rounded-xl border px-4 py-4 text-sm ${
                isLie
                  ? "border-rose-700 bg-rose-950/40 text-rose-300"
                  : "border-emerald-800 bg-emerald-950/30 text-emerald-300"
              }`}
            >
              <span className="mr-3 font-mono opacity-60">{i + 1}.</span>
              {statement}
              {isLie && <span className="ml-2 text-xs font-medium text-rose-500"> LIE</span>}
            </div>
          );
        })}
      </div>

      {correctVoters.length > 0 && (
        <p className="text-center text-sm text-zinc-400">
          Guessed correctly:{" "}
          <span className="text-emerald-400">
            {correctVoters.map((id) => playerName(players, id)).join(", ")}
          </span>
        </p>
      )}

      {isStoryteller && (
        <p className="text-center text-sm text-zinc-400">
          You fooled {(gameState.voted_count ?? 0) - correctVoters.length} out of{" "}
          {gameState.voted_count ?? 0} voters.
        </p>
      )}

      <Leaderboard players={players} scores={gameState.scores} />

      {isHost && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => sendCommand({ type: "next_round" })}
            className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400"
          >
            {isLast ? "See final results" : "Next round"}
          </button>
        </div>
      )}
      {!isHost && (
        <p className="text-center text-sm text-zinc-600">Waiting for the host to continue…</p>
      )}
    </div>
  );
}

export function GameView() {
  const router = useRouter();
  const room = useRoomStore((state) => state.room);
  const selfPlayerId = useRoomStore((state) => state.selfPlayerId);
  const gameOver = useRoomStore((state) => state.gameOver);
  const revealData = useRoomStore((state) => state.revealData);
  const sendCommand = useRoomStore((state) => state.sendCommand);
  const disconnect = useRoomStore((state) => state.disconnect);

  if (!room?.game_state) return null;

  const { game_state: gameState, players } = room;
  const self = players.find((p) => p.id === selfPlayerId);
  const isHost = self?.is_host ?? false;

  function leave() {
    sendCommand({ type: "leave_room" });
    clearPlayerId(room!.code);
    disconnect();
    router.push("/");
  }

  if (gameState.phase === "game_over" && gameOver) {
    return (
      <GameOverScreen
        players={players}
        scores={gameOver.scores}
        selfPlayerId={selfPlayerId}
        onLeave={leave}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between text-sm text-zinc-500">
        <span>
          Round {gameState.round_number} / {gameState.total_rounds}
        </span>
        <span className="rounded-full bg-zinc-800 px-3 py-1 capitalize text-zinc-300">
          {gameState.phase}
        </span>
      </div>

      {gameState.phase === "submitting" && (
        <SubmittingView
          selfPlayerId={selfPlayerId}
          gameState={gameState}
          players={players}
          sendCommand={sendCommand}
        />
      )}

      {gameState.phase === "voting" && (
        <VotingView
          selfPlayerId={selfPlayerId}
          gameState={gameState}
          players={players}
          sendCommand={sendCommand}
        />
      )}

      {gameState.phase === "reveal" && (
        <RevealView
          selfPlayerId={selfPlayerId}
          gameState={gameState}
          players={players}
          revealData={revealData}
          sendCommand={sendCommand}
          isHost={isHost}
        />
      )}
    </div>
  );
}
