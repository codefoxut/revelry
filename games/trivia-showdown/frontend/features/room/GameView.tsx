"use client";

import { useRouter } from "next/navigation";
import { useRoomStore } from "@/store/roomStore";
import { clearPlayerId } from "@/lib/session";
import { avatarEmoji } from "@/lib/avatars";
import type { Player } from "@/types/room";
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
  winnerId,
  selfPlayerId,
  onLeave,
}: {
  players: Player[];
  scores: Record<string, number>;
  winnerId: string | null;
  selfPlayerId: string | null;
  onLeave: () => void;
}) {
  const winnerName = winnerId ? playerName(players, winnerId) : null;

  return (
    <div className="flex flex-col items-center gap-6 text-center">
      <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-1 text-sm font-medium text-zinc-400">
        Game over
      </span>
      <h2 className="text-2xl font-semibold tracking-tight">
        {winnerName ? (
          <>
            <span className="text-rose-500">{winnerName}</span> wins!
          </>
        ) : (
          "It's a tie!"
        )}
      </h2>
      {winnerId === selfPlayerId && (
        <p className="text-zinc-400">Nice buzzing.</p>
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

export function GameView() {
  const router = useRouter();
  const room = useRoomStore((state) => state.room);
  const selfPlayerId = useRoomStore((state) => state.selfPlayerId);
  const gameOver = useRoomStore((state) => state.gameOver);
  const lastJudged = useRoomStore((state) => state.lastJudged);
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
        winnerId={gameOver.winnerId}
        selfPlayerId={selfPlayerId}
        onLeave={leave}
      />
    );
  }

  const buzzedName = playerName(players, gameState.buzzed_player_id);
  const answering = gameState.phase === "answering";
  const revealed = gameState.phase === "revealed";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between text-sm text-zinc-500">
        <span>
          Question {gameState.round_number} / {gameState.total_questions}
        </span>
        {gameState.category && (
          <span className="rounded-full bg-zinc-800 px-3 py-1 text-zinc-300">{gameState.category}</span>
        )}
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6 text-center">
        <p className="text-xl font-medium text-zinc-50">{gameState.question}</p>
        {revealed && gameState.answer && (
          <p className="mt-4 text-lg text-emerald-400">Answer: {gameState.answer}</p>
        )}
      </div>

      {answering && (
        <p className="text-center text-lg font-medium text-rose-400">
          {buzzedName} buzzed in{buzzedName === self?.display_name ? " — you're up!" : "!"}
        </p>
      )}

      {lastJudged && !answering && (
        <p
          className={`text-center text-sm ${lastJudged.correct ? "text-emerald-400" : "text-zinc-500"}`}
        >
          {playerName(players, lastJudged.playerId)}{" "}
          {lastJudged.correct ? `got it right (+${lastJudged.scoreDelta})` : "was incorrect"}
        </p>
      )}

      {isHost ? (
        <HostControls sendCommand={sendCommand} gameState={gameState} buzzedName={buzzedName} />
      ) : (
        <ContestantControls
          sendCommand={sendCommand}
          gameState={gameState}
          selfPlayerId={selfPlayerId}
        />
      )}

      <Leaderboard players={players} scores={gameState.scores} />
    </div>
  );
}

function HostControls({
  sendCommand,
  gameState,
  buzzedName,
}: {
  sendCommand: (command: ClientCommand) => void;
  gameState: { phase: string; total_questions: number; round_number: number };
  buzzedName: string;
}) {
  if (gameState.phase === "question_open") {
    return (
      <div className="flex flex-col items-center gap-2">
        <p className="text-sm text-zinc-500">Waiting for a contestant to buzz in…</p>
        <button
          type="button"
          onClick={() => sendCommand({ type: "reveal" })}
          className="h-10 rounded-full border border-zinc-700 px-6 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500"
        >
          Reveal answer
        </button>
      </div>
    );
  }

  if (gameState.phase === "answering") {
    return (
      <div className="flex flex-col items-center gap-2">
        <p className="text-sm text-zinc-500">Did {buzzedName} answer correctly?</p>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => sendCommand({ type: "judge_answer", correct: true })}
            className="h-12 rounded-full bg-emerald-500 px-8 font-medium text-white transition-colors hover:bg-emerald-400"
          >
            Correct
          </button>
          <button
            type="button"
            onClick={() => sendCommand({ type: "judge_answer", correct: false })}
            className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400"
          >
            Incorrect
          </button>
        </div>
      </div>
    );
  }

  if (gameState.phase === "revealed") {
    const isLast = gameState.round_number >= gameState.total_questions;
    return (
      <div className="flex justify-center">
        <button
          type="button"
          onClick={() => sendCommand({ type: "next_question" })}
          className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400"
        >
          {isLast ? "See final results" : "Next question"}
        </button>
      </div>
    );
  }

  return null;
}

function ContestantControls({
  sendCommand,
  gameState,
  selfPlayerId,
}: {
  sendCommand: (command: ClientCommand) => void;
  gameState: { phase: string; buzzed_player_id: string | null; locked_out: string[] };
  selfPlayerId: string | null;
}) {
  const lockedOut = selfPlayerId ? gameState.locked_out.includes(selfPlayerId) : false;
  const isMe = gameState.buzzed_player_id === selfPlayerId;
  const canBuzz = gameState.phase === "question_open" && !lockedOut;

  if (gameState.phase === "answering") {
    return (
      <p className="text-center text-sm text-zinc-500">
        {isMe ? "Say your answer out loud!" : "Waiting for the host to judge…"}
      </p>
    );
  }

  if (gameState.phase === "revealed") {
    return <p className="text-center text-sm text-zinc-500">Waiting for the next question…</p>;
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={() => sendCommand({ type: "buzz_in" })}
        disabled={!canBuzz}
        className="h-32 w-32 rounded-full bg-rose-500 text-xl font-bold text-white transition-colors hover:bg-rose-400 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-500"
      >
        BUZZ
      </button>
      {lockedOut && <p className="text-sm text-zinc-600">You&rsquo;re locked out for this question.</p>}
    </div>
  );
}
