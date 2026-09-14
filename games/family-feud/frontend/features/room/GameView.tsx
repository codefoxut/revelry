"use client";

import { useRouter } from "next/navigation";
import { useRoomStore } from "@/store/roomStore";
import { clearPlayerId } from "@/lib/session";
import type { BoardSlot, Player } from "@/types/room";
import type { ClientCommand } from "@/types/ws-events";

const TEAM_LABEL: Record<"a" | "b", string> = { a: "Team A", b: "Team B" };
const TEAM_COLOR: Record<"a" | "b", string> = {
  a: "text-blue-400",
  b: "text-red-400",
};
const TEAM_BG: Record<"a" | "b", string> = {
  a: "bg-blue-600 hover:bg-blue-500",
  b: "bg-red-600 hover:bg-red-500",
};

function teamLabel(team: "a" | "b" | null | undefined): string {
  if (!team) return "";
  return TEAM_LABEL[team];
}

function teamColor(team: "a" | "b" | null | undefined): string {
  if (!team) return "text-zinc-400";
  return TEAM_COLOR[team];
}

function Board({ board, phase, onReveal }: {
  board: BoardSlot[];
  phase: string;
  onReveal?: (index: number) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {board.map((slot, index) => {
        const clickable = !slot.revealed && (phase === "answering" || phase === "steal") && !!onReveal;
        return (
          <button
            key={index}
            type="button"
            disabled={!clickable}
            onClick={() => onReveal?.(index)}
            className={`flex flex-col items-center justify-center rounded-xl border px-4 py-4 transition-colors ${
              slot.revealed
                ? "border-amber-600 bg-amber-950/40 text-zinc-50"
                : clickable
                ? "cursor-pointer border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-amber-600 hover:bg-zinc-700"
                : "border-zinc-800 bg-zinc-900 text-zinc-600"
            }`}
          >
            <span className="text-xs font-medium text-zinc-500">#{index + 1}</span>
            {slot.revealed ? (
              <>
                <span className="mt-1 text-center text-sm font-semibold">{slot.text}</span>
                <span className="mt-1 font-mono text-lg font-bold text-amber-400">{slot.points}</span>
              </>
            ) : (
              <span className="mt-2 text-sm text-zinc-600">
                {clickable ? "Reveal" : "Hidden"}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function StrikeIndicator({ strikes, max = 3 }: { strikes: number; max?: number }) {
  return (
    <div className="flex items-center gap-1" aria-label={`${strikes} of ${max} strikes`}>
      {Array.from({ length: max }).map((_, i) => (
        <span
          key={i}
          className={`h-4 w-4 rounded-full border ${i < strikes ? "border-red-500 bg-red-500" : "border-zinc-700 bg-zinc-900"}`}
        />
      ))}
    </div>
  );
}

function ScoreBar({ teamScores, players, teamOf }: {
  teamScores: Record<"a" | "b", number>;
  players: Player[];
  teamOf: Record<string, "a" | "b">;
}) {
  const aNames = players.filter((p) => teamOf[p.id] === "a").map((p) => p.display_name).join(", ");
  const bNames = players.filter((p) => teamOf[p.id] === "b").map((p) => p.display_name).join(", ");

  return (
    <div className="grid grid-cols-2 gap-3 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
      <div className="flex flex-col items-center gap-1">
        <span className="text-xs font-semibold text-blue-400">Team A</span>
        <span className="font-mono text-3xl font-bold text-zinc-50">{teamScores.a}</span>
        <span className="text-center text-xs text-zinc-500">{aNames}</span>
      </div>
      <div className="flex flex-col items-center gap-1">
        <span className="text-xs font-semibold text-red-400">Team B</span>
        <span className="font-mono text-3xl font-bold text-zinc-50">{teamScores.b}</span>
        <span className="text-center text-xs text-zinc-500">{bNames}</span>
      </div>
    </div>
  );
}

function GameOverScreen({
  teamScores,
  winningTeam,
  selfTeam,
  onLeave,
}: {
  teamScores: Record<"a" | "b", number>;
  winningTeam: "a" | "b" | null;
  selfTeam: "a" | "b" | undefined;
  onLeave: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-6 text-center">
      <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-1 text-sm font-medium text-zinc-400">
        Game over
      </span>
      <h2 className="text-2xl font-semibold tracking-tight">
        {winningTeam ? (
          <>
            <span className={teamColor(winningTeam)}>{teamLabel(winningTeam)}</span> wins!
          </>
        ) : (
          "It's a tie!"
        )}
      </h2>
      {winningTeam && winningTeam === selfTeam && (
        <p className="text-zinc-400">Your team won — well played!</p>
      )}
      <div className="grid w-full grid-cols-2 gap-3">
        {(["a", "b"] as const).map((team) => (
          <div
            key={team}
            className={`flex flex-col items-center rounded-xl border p-4 ${
              team === "a" ? "border-blue-800 bg-blue-950/20" : "border-red-800 bg-red-950/20"
            }`}
          >
            <span className={`text-sm font-semibold ${teamColor(team)}`}>{teamLabel(team)}</span>
            <span className="font-mono text-4xl font-bold text-zinc-50">{teamScores[team]}</span>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={onLeave}
        className="h-12 rounded-full bg-amber-500 px-8 font-medium text-zinc-950 transition-colors hover:bg-amber-400"
      >
        Back home
      </button>
    </div>
  );
}

export function GameView() {
  const router = useRouter();
  const room = useRoomStore((state) => state.room);
  const selfPlayerId = useRoomStore((state) => state.selfPlayerId);
  const gameOver = useRoomStore((state) => state.gameOver);
  const lastRoundOver = useRoomStore((state) => state.lastRoundOver);
  const sendCommand = useRoomStore((state) => state.sendCommand);
  const disconnect = useRoomStore((state) => state.disconnect);

  if (!room?.game_state) return null;

  const { game_state: gs, players } = room;
  const self = players.find((p) => p.id === selfPlayerId);
  const isHost = self?.is_host ?? false;
  const selfTeam = selfPlayerId ? gs.team_of[selfPlayerId] : undefined;

  function leave() {
    sendCommand({ type: "leave_room" });
    clearPlayerId(room!.code);
    disconnect();
    router.push("/");
  }

  if (gs.phase === "game_over" && gameOver) {
    return (
      <GameOverScreen
        teamScores={gameOver.team_scores}
        winningTeam={gameOver.winning_team}
        selfTeam={selfTeam}
        onLeave={leave}
      />
    );
  }

  const controlling = gs.controlling_team;

  return (
    <div className="flex flex-col gap-5">
      {/* Round / progress header */}
      <div className="flex items-center justify-between text-sm text-zinc-500">
        <span>Round {gs.round_number} / {gs.total_rounds}</span>
        {controlling && (
          <span className={`rounded-full bg-zinc-800 px-3 py-1 font-medium ${teamColor(controlling)}`}>
            {teamLabel(controlling)} buzzing
          </span>
        )}
      </div>

      {/* Prompt */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5 text-center">
        <p className="text-sm text-zinc-500">{gs.answer_count} answers on the board</p>
        <p className="mt-2 text-xl font-semibold text-zinc-50">{gs.prompt}</p>
      </div>

      {/* Strikes */}
      {gs.phase !== "question_open" && (
        <div className="flex items-center justify-center gap-3">
          <span className="text-sm text-zinc-500">Strikes:</span>
          <StrikeIndicator strikes={gs.strikes} />
        </div>
      )}

      {/* Steal banner */}
      {gs.phase === "steal" && gs.controlling_team && (
        <div className={`rounded-lg border px-4 py-3 text-center ${
          gs.controlling_team === "a"
            ? "border-red-800 bg-red-950/30 text-red-300"
            : "border-blue-800 bg-blue-950/30 text-blue-300"
        }`}>
          <span className="font-semibold">
            {teamLabel(gs.controlling_team === "a" ? "b" : "a")} — steal opportunity!
          </span>
        </div>
      )}

      {/* Board */}
      <Board
        board={gs.board}
        phase={gs.phase}
        onReveal={isHost && (gs.phase === "answering" || gs.phase === "steal")
          ? (i) => {
              if (gs.phase === "steal") {
                sendCommand({ type: "steal_reveal", slot_index: i });
              } else {
                sendCommand({ type: "reveal_slot", slot_index: i });
              }
            }
          : undefined}
      />

      {/* Round over full board reveal */}
      {gs.phase === "round_over" && lastRoundOver && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
          <p className="mb-2 text-center text-sm font-medium text-zinc-400">
            {lastRoundOver.team_awarded
              ? `${teamLabel(lastRoundOver.team_awarded)} earns ${lastRoundOver.points} pts`
              : `No points scored this round`}
          </p>
          <div className="grid grid-cols-2 gap-1 sm:grid-cols-3">
            {lastRoundOver.board.map((slot, i) => (
              <div
                key={i}
                className="flex flex-col items-center rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-2"
              >
                <span className="text-xs text-zinc-500">#{i + 1}</span>
                <span className="text-center text-xs font-medium text-zinc-200">{slot.text}</span>
                <span className="font-mono text-sm font-bold text-amber-400">{slot.points}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Score bar */}
      <ScoreBar teamScores={gs.team_scores} players={players} teamOf={gs.team_of} />

      {/* Controls */}
      {isHost ? (
        <HostControls sendCommand={sendCommand} phase={gs.phase} />
      ) : (
        <ContestantControls
          sendCommand={sendCommand}
          phase={gs.phase}
          selfPlayerId={selfPlayerId}
          controllingTeam={gs.controlling_team}
          selfTeam={selfTeam}
        />
      )}
    </div>
  );
}

function HostControls({
  sendCommand,
  phase,
}: {
  sendCommand: (cmd: ClientCommand) => void;
  phase: string;
}) {
  if (phase === "question_open") {
    return (
      <p className="text-center text-sm text-zinc-500">
        Waiting for a player to buzz in…
      </p>
    );
  }

  if (phase === "answering") {
    return (
      <div className="flex flex-col items-center gap-3">
        <p className="text-sm text-zinc-500">Reveal an answer or call a strike:</p>
        <button
          type="button"
          onClick={() => sendCommand({ type: "strike" })}
          className="h-12 w-full max-w-xs rounded-full bg-red-600 px-8 font-semibold text-white transition-colors hover:bg-red-500"
        >
          ✗ Strike
        </button>
      </div>
    );
  }

  if (phase === "steal") {
    return (
      <div className="flex flex-col items-center gap-3">
        <p className="text-sm text-zinc-500">Stealing team — reveal a correct answer or miss:</p>
        <button
          type="button"
          onClick={() => sendCommand({ type: "steal_miss" })}
          className="h-12 w-full max-w-xs rounded-full bg-zinc-700 px-8 font-medium text-zinc-300 transition-colors hover:bg-zinc-600"
        >
          Miss — award points to controlling team
        </button>
      </div>
    );
  }

  if (phase === "round_over") {
    return (
      <div className="flex justify-center">
        <button
          type="button"
          onClick={() => sendCommand({ type: "next_round" })}
          className="h-12 rounded-full bg-amber-500 px-8 font-medium text-zinc-950 transition-colors hover:bg-amber-400"
        >
          Next round
        </button>
      </div>
    );
  }

  return null;
}

function ContestantControls({
  sendCommand,
  phase,
  selfPlayerId,
  controllingTeam,
  selfTeam,
}: {
  sendCommand: (cmd: ClientCommand) => void;
  phase: string;
  selfPlayerId: string | null;
  controllingTeam: "a" | "b" | null;
  selfTeam: "a" | "b" | undefined;
}) {
  if (phase === "question_open") {
    const canBuzz = !!selfTeam;
    return (
      <div className="flex flex-col items-center gap-2">
        <button
          type="button"
          onClick={() => sendCommand({ type: "buzz_in" })}
          disabled={!canBuzz}
          className={`h-32 w-32 rounded-full text-xl font-bold transition-colors ${
            canBuzz
              ? `text-zinc-950 ${selfTeam ? TEAM_BG[selfTeam] : "bg-amber-500 hover:bg-amber-400"}`
              : "cursor-not-allowed bg-zinc-700 text-zinc-500"
          }`}
        >
          BUZZ
        </button>
        {!canBuzz && (
          <p className="text-sm text-zinc-600">You need to be on a team to buzz in.</p>
        )}
      </div>
    );
  }

  if (phase === "answering") {
    const isControlling = selfTeam && controllingTeam === selfTeam;
    return (
      <p className="text-center text-sm text-zinc-500">
        {isControlling
          ? "Your team is answering — say your answer out loud!"
          : "Waiting for the controlling team to answer…"}
      </p>
    );
  }

  if (phase === "steal") {
    const isStealingTeam = selfTeam && controllingTeam && selfTeam !== controllingTeam;
    return (
      <p className="text-center text-sm text-zinc-500">
        {isStealingTeam
          ? "Your team is stealing — say a correct answer out loud!"
          : "Waiting for the host to process the steal…"}
      </p>
    );
  }

  if (phase === "round_over") {
    return <p className="text-center text-sm text-zinc-500">Waiting for the next round…</p>;
  }

  return null;
}
