"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRoomStore } from "@/store/roomStore";
import type { Player } from "@/types/room";

export function GameView() {
  const router = useRouter();
  const room = useRoomStore((state) => state.room);
  const selfPlayerId = useRoomStore((state) => state.selfPlayerId);
  const myRole = useRoomStore((state) => state.myRole);
  const nightResult = useRoomStore((state) => state.nightResult);
  const eliminationResult = useRoomStore((state) => state.eliminationResult);
  const gameOver = useRoomStore((state) => state.gameOver);
  const investigationResult = useRoomStore((state) => state.investigationResult);
  const votes = useRoomStore((state) => state.votes);
  const sendCommand = useRoomStore((state) => state.sendCommand);

  const phase = room?.game_state?.phase;
  const roundNumber = room?.game_state?.round_number;

  if (!room || !room.game_state) return null;

  const self = room.players.find((player) => player.id === selfPlayerId);
  const isHost = self?.is_host ?? false;
  const aliveIds = new Set(room.game_state.alive_player_ids);
  const selfAlive = selfPlayerId ? aliveIds.has(selfPlayerId) : false;
  const alivePlayers = room.players.filter((player) => aliveIds.has(player.id));

  function submitNightAction(targetId: string) {
    sendCommand({ type: "night_action", target_player_id: targetId });
  }

  function submitVote(targetId: string) {
    sendCommand({ type: "cast_vote", target_player_id: targetId });
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
        <h1 className="text-3xl font-semibold capitalize tracking-tight">
          {gameOver.winningTeam} wins
        </h1>
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
          <span className="text-xl font-semibold text-rose-400">{myRole.display_name}</span>
          <span className="text-xs uppercase tracking-wide text-zinc-600">{myRole.team} team</span>
          <p className="mt-1 text-center text-sm text-zinc-400">{myRole.description}</p>
          {!selfAlive && (
            <span className="mt-1 rounded-full bg-zinc-800 px-3 py-0.5 text-xs text-zinc-400">
              You have been eliminated
            </span>
          )}
        </div>
      )}

      <div className="flex flex-col items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
        <span className="rounded-full border border-rose-900 bg-rose-950/50 px-4 py-1 text-sm font-medium capitalize text-rose-300">
          {phase} &middot; Round {roundNumber}
        </span>

        {investigationResult && phase === "night" && (
          <p className="text-center text-sm text-zinc-300">
            Investigation result: that player is on the{" "}
            <span className="font-medium capitalize text-rose-400">{investigationResult.team}</span> team.
          </p>
        )}

        {nightResult && (phase === "day" || phase === "voting" || phase === "elimination") && (
          <p className="text-center text-sm text-zinc-400">
            {nightResult.eliminatedPlayerId
              ? `${playerName(room.players, nightResult.eliminatedPlayerId)} was killed overnight.`
              : "No one was killed overnight."}
          </p>
        )}

        {eliminationResult && phase === "elimination" && (
          <p className="text-center text-sm text-zinc-400">
            {eliminationResult.eliminatedPlayerId
              ? `The town voted out ${playerName(room.players, eliminationResult.eliminatedPlayerId)}.`
              : "The vote ended in a tie — no one was eliminated."}
          </p>
        )}

        {phase === "night" && selfAlive && myRole?.acts_at_night && (
          <TargetPicker
            key={`night-${roundNumber}`}
            label="Choose your target"
            players={alivePlayers}
            onSelect={submitNightAction}
          />
        )}
        {phase === "night" && selfAlive && !myRole?.acts_at_night && (
          <p className="text-center text-sm text-zinc-600">
            Your role has no night action. Waiting for the others&hellip;
          </p>
        )}
        {phase === "night" && !selfAlive && (
          <p className="text-center text-sm text-zinc-600">You&rsquo;re out, but you can keep watching.</p>
        )}

        {phase === "voting" && selfAlive && (
          <TargetPicker
            key={`voting-${roundNumber}`}
            label="Vote to eliminate"
            players={alivePlayers}
            onSelect={submitVote}
            voteCounts={countVotes(votes)}
          />
        )}
        {phase === "voting" && !selfAlive && (
          <p className="text-center text-sm text-zinc-600">You&rsquo;re out, but you can keep watching.</p>
        )}

        {isHost && (
          <button
            type="button"
            onClick={advancePhase}
            className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400"
          >
            Advance phase
          </button>
        )}
      </div>
    </div>
  );
}

function TargetPicker({
  label,
  players,
  onSelect,
  voteCounts,
}: {
  label: string;
  players: Player[];
  onSelect: (targetId: string) => void;
  voteCounts?: Record<string, number>;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  function handleSelect(targetId: string) {
    setSelectedId(targetId);
    onSelect(targetId);
  }

  return (
    <div className="flex w-full flex-col gap-2">
      <span className="text-center text-xs uppercase tracking-wide text-zinc-500">{label}</span>
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
              <span>{player.display_name}</span>
              {voteCounts && voteCounts[player.id] ? (
                <span className="text-xs text-zinc-500">{voteCounts[player.id]} vote(s)</span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
    </div>
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
