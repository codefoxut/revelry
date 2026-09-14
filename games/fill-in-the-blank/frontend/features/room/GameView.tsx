"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRoomStore } from "@/store/roomStore";
import { clearPlayerId } from "@/lib/session";
import { avatarEmoji } from "@/lib/avatars";
import type { Player, GameState, Submission, VoteResult } from "@/types/room";
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
          <span className="font-mono text-lg text-violet-400">{scores[player.id] ?? 0}</span>
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
            <span className="text-violet-400">{winner.display_name}</span> wins!
          </>
        ) : null}
      </h2>
      {winner?.id === selfPlayerId && !isTie && (
        <p className="text-zinc-400">Most creative mind in the room. Well played.</p>
      )}
      <Leaderboard players={players} scores={scores} />
      <button
        type="button"
        onClick={onLeave}
        className="h-12 rounded-full bg-violet-600 px-8 font-medium text-white transition-colors hover:bg-violet-500"
      >
        Back home
      </button>
    </div>
  );
}

function PromptOpenView({
  selfPlayerId,
  gameState,
  players,
  sendCommand,
  isHost,
}: {
  selfPlayerId: string | null;
  gameState: GameState;
  players: Player[];
  sendCommand: (cmd: ClientCommand) => void;
  isHost: boolean;
}) {
  const totalPlayers = players.filter((p) => !p.is_spectator).length;
  const [answer, setAnswer] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit() {
    if (!answer.trim()) {
      setError("Answer can't be empty.");
      return;
    }
    setError(null);
    setSubmitted(true);
    sendCommand({ type: "submit_answer", text: answer.trim() });
  }

  const blank = gameState.prompt?.replace("___", "______") ?? "";

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-xl border border-violet-800 bg-violet-950/30 px-5 py-4 text-center">
        <p className="text-lg font-medium leading-relaxed text-violet-100">{blank}</p>
      </div>

      <p className="text-center text-sm text-zinc-500">
        {gameState.submitted_count} / {totalPlayers} submitted
      </p>

      {!submitted ? (
        <div className="flex flex-col gap-3">
          <textarea
            autoFocus
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Your answer…"
            maxLength={200}
            rows={2}
            className="resize-none rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-zinc-50 outline-none focus:border-violet-500"
          />
          {error && (
            <p role="alert" className="text-center text-sm text-rose-400">
              {error}
            </p>
          )}
          <button
            type="button"
            onClick={handleSubmit}
            className="h-12 rounded-full bg-violet-600 px-8 font-medium text-white transition-colors hover:bg-violet-500"
          >
            Submit
          </button>
        </div>
      ) : (
        <p className="text-center text-sm text-emerald-400">Answer submitted! Waiting for others…</p>
      )}

      {isHost && (
        <div className="flex flex-col items-center gap-2 border-t border-zinc-800 pt-4">
          <button
            type="button"
            onClick={() => sendCommand({ type: "reveal" })}
            className="h-10 rounded-full border border-zinc-700 px-6 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500 hover:text-zinc-100"
          >
            Reveal submissions
          </button>
          <p className="text-xs text-zinc-600">
            Skips remaining submissions and shows what was received.
          </p>
        </div>
      )}
    </div>
  );
}

function SubmissionsRevealedView({
  gameState,
  sendCommand,
  isHost,
}: {
  selfPlayerId: string | null;
  gameState: GameState;
  sendCommand: (cmd: ClientCommand) => void;
  isHost: boolean;
}) {
  const submissions: Submission[] = gameState.submissions ?? [];

  return (
    <div className="flex flex-col gap-4">
      <p className="text-center text-sm text-zinc-400">
        All answers are in — read them before voting!
      </p>

      <div className="flex flex-col gap-3">
        {submissions.map((sub, i) => (
          <div
            key={sub.submission_id}
            className="rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-4 text-sm text-zinc-200"
          >
            <span className="mr-3 font-mono text-zinc-500">{i + 1}.</span>
            {sub.text}
          </div>
        ))}
        {submissions.length === 0 && (
          <p className="text-center text-sm text-zinc-600">No one submitted an answer.</p>
        )}
      </div>

      {isHost && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => sendCommand({ type: "start_vote" })}
            className="h-12 rounded-full bg-violet-600 px-8 font-medium text-white transition-colors hover:bg-violet-500"
          >
            Start vote
          </button>
        </div>
      )}
      {!isHost && (
        <p className="text-center text-sm text-zinc-600">Waiting for the host to open voting…</p>
      )}
    </div>
  );
}

function VotingView({
  gameState,
  players,
  sendCommand,
}: {
  gameState: GameState;
  players: Player[];
  sendCommand: (cmd: ClientCommand) => void;
}) {
  const totalVoters = players.filter((p) => !p.is_spectator).length;
  const submissions: Submission[] = gameState.submissions ?? [];
  const [votedId, setVotedId] = useState<string | null>(null);
  const lastError = useRoomStore((state) => state.lastError);

  // If the server rejects the vote (self-vote), unlock so the player can pick again.
  const isRejected = lastError?.code === "permission_denied" && votedId !== null;
  const effectiveVotedId = isRejected ? null : votedId;

  function castVote(submissionId: string) {
    if (effectiveVotedId) return;
    setVotedId(submissionId);
    sendCommand({ type: "cast_vote", submission_id: submissionId });
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-center text-sm text-zinc-400">
        Which answer is your favourite? You can&rsquo;t vote for your own.
      </p>

      <div className="flex flex-col gap-3">
        {submissions.map((sub, i) => (
          <button
            key={sub.submission_id}
            type="button"
            onClick={() => castVote(sub.submission_id)}
            disabled={!!effectiveVotedId}
            className={`rounded-xl border px-4 py-4 text-left text-sm transition-colors ${
              effectiveVotedId === sub.submission_id
                ? "border-violet-600 bg-violet-950/40 text-violet-200"
                : effectiveVotedId
                  ? "cursor-default border-zinc-800 bg-zinc-900 text-zinc-500"
                  : "border-zinc-700 bg-zinc-900 text-zinc-50 hover:border-violet-500 hover:bg-zinc-800"
            }`}
          >
            <span className="mr-3 font-mono text-zinc-500">{i + 1}.</span>
            {sub.text}
          </button>
        ))}
        {submissions.length === 0 && (
          <p className="text-center text-sm text-zinc-600">No submissions to vote on.</p>
        )}
      </div>

      {isRejected && (
        <p role="alert" className="text-center text-sm text-rose-400">
          You can&rsquo;t vote for your own answer. Pick a different one.
        </p>
      )}

      {effectiveVotedId && !isRejected && (
        <p className="text-center text-sm text-emerald-400">Vote cast! Waiting for others…</p>
      )}

      <p className="text-center text-sm text-zinc-600">
        {gameState.voted_count} / {totalVoters} voted
      </p>
    </div>
  );
}

function ResultsView({
  selfPlayerId,
  gameState,
  players,
  lastRoundDelta,
  sendCommand,
  isHost,
}: {
  selfPlayerId: string | null;
  gameState: GameState;
  players: Player[];
  lastRoundDelta: Record<string, number> | null;
  sendCommand: (cmd: ClientCommand) => void;
  isHost: boolean;
}) {
  const results: VoteResult[] = gameState.results ?? [];
  const isLast = gameState.question_number >= gameState.total_questions;

  return (
    <div className="flex flex-col gap-5">
      <p className="text-center text-sm text-zinc-400">The votes are in!</p>

      <div className="flex flex-col gap-3">
        {results
          .slice()
          .sort((a, b) => b.votes - a.votes)
          .map((entry) => {
            const author = players.find((p) => p.id === entry.author_id);
            const isSelf = entry.author_id === selfPlayerId;
            const delta = lastRoundDelta?.[entry.author_id] ?? 0;
            return (
              <div
                key={entry.submission_id}
                className={`rounded-xl border px-4 py-4 text-sm ${
                  entry.votes > 0
                    ? "border-violet-800 bg-violet-950/30"
                    : "border-zinc-800 bg-zinc-900"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className={entry.votes > 0 ? "text-violet-100" : "text-zinc-300"}>
                    {entry.text}
                  </p>
                  <span className="shrink-0 font-mono text-sm text-violet-400">
                    {entry.votes} {entry.votes === 1 ? "vote" : "votes"}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-xs text-zinc-500">
                    {avatarEmoji(author?.avatar ?? "")} {author?.display_name ?? "Unknown"}
                    {isSelf && <span className="ml-1 text-zinc-600">(you)</span>}
                  </span>
                  {delta > 0 && (
                    <span className="rounded-full bg-violet-900/60 px-2 py-0.5 text-xs font-medium text-violet-300">
                      +{delta}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        {results.length === 0 && (
          <p className="text-center text-sm text-zinc-600">Nobody voted this round.</p>
        )}
      </div>

      <Leaderboard players={players} scores={gameState.scores} />

      {isHost && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => sendCommand({ type: "next_prompt" })}
            className="h-12 rounded-full bg-violet-600 px-8 font-medium text-white transition-colors hover:bg-violet-500"
          >
            {isLast ? "See final results" : "Next prompt"}
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
  const lastRoundDelta = useRoomStore((state) => state.lastRoundDelta);
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
          Prompt {gameState.question_number} / {gameState.total_questions}
        </span>
        <span className="rounded-full bg-zinc-800 px-3 py-1 capitalize text-zinc-300">
          {gameState.phase.replace(/_/g, " ")}
        </span>
      </div>

      {gameState.phase === "prompt_open" && (
        <PromptOpenView
          selfPlayerId={selfPlayerId}
          gameState={gameState}
          players={players}
          sendCommand={sendCommand}
          isHost={isHost}
        />
      )}

      {gameState.phase === "submissions_revealed" && (
        <SubmissionsRevealedView
          selfPlayerId={selfPlayerId}
          gameState={gameState}
          sendCommand={sendCommand}
          isHost={isHost}
        />
      )}

      {gameState.phase === "voting" && (
        <VotingView
          gameState={gameState}
          players={players}
          sendCommand={sendCommand}
        />
      )}

      {gameState.phase === "results" && (
        <ResultsView
          selfPlayerId={selfPlayerId}
          gameState={gameState}
          players={players}
          lastRoundDelta={lastRoundDelta}
          sendCommand={sendCommand}
          isHost={isHost}
        />
      )}
    </div>
  );
}
