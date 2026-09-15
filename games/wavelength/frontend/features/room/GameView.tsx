"use client";

import { useState, type ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import { useRoomStore } from "@/store/roomStore";
import { avatarEmoji } from "@/lib/avatars";
import type { Player } from "@/types/room";

export function GameView() {
  const router = useRouter();
  const room = useRoomStore((state) => state.room);
  const selfPlayerId = useRoomStore((state) => state.selfPlayerId);
  const psychicSecret = useRoomStore((state) => state.psychicSecret);
  const lastError = useRoomStore((state) => state.lastError);
  const sendCommand = useRoomStore((state) => state.sendCommand);

  const gameState = room?.game_state;

  if (!room || !gameState) return null;

  const phase = gameState.phase;
  const isPsychic = selfPlayerId === gameState.psychic_id;
  const psychicPlayer = room.players.find((p) => p.id === gameState.psychic_id);

  const playerById = Object.fromEntries(room.players.map((p) => [p.id, p]));

  if (phase === "game_over") {
    return (
      <GameOverScreen
        scores={gameState.scores}
        players={room.players}
        onHome={() => router.push("/")}
      />
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <RoundHeader
        roundNumber={gameState.round_number}
        totalRounds={gameState.total_rounds}
        psychicPlayer={psychicPlayer}
        isPsychic={isPsychic}
      />

      {lastError && (
        <p role="alert" className="rounded-lg border border-rose-900 bg-rose-950/50 px-4 py-2 text-center text-sm text-rose-300">
          {lastError.message}
        </p>
      )}

      {phase === "clue_giving" && (
        <ClueGivingPhase
          isPsychic={isPsychic}
          psychicSecret={psychicSecret}
          leftLabel={gameState.left_label}
          rightLabel={gameState.right_label}
          onGiveClue={(clueText) => sendCommand({ type: "give_clue", clue_text: clueText })}
        />
      )}

      {phase === "guessing" && (
        <GuessingPhase
          isPsychic={isPsychic}
          leftLabel={gameState.left_label}
          rightLabel={gameState.right_label}
          clueText={gameState.clue_text}
          guessedCount={gameState.guessed_count}
          totalGuessers={room.players.filter((p) => !p.is_spectator).length - 1}
          onSubmitGuess={(pos) => sendCommand({ type: "submit_guess", position: pos })}
          onForceReveal={() => sendCommand({ type: "reveal" })}
        />
      )}

      {phase === "reveal" && (
        <RevealPhase
          leftLabel={gameState.left_label}
          rightLabel={gameState.right_label}
          targetPosition={gameState.target_position}
          guesses={gameState.guesses}
          pointsAwarded={gameState.points_awarded}
          scores={gameState.scores}
          players={room.players}
          playerById={playerById}
          onNextRound={() => sendCommand({ type: "next_round" })}
        />
      )}

      <Leaderboard scores={gameState.scores} players={room.players} />
    </div>
  );
}

// ---- Round header ----

function RoundHeader({
  roundNumber,
  totalRounds,
  psychicPlayer,
  isPsychic,
}: {
  roundNumber: number;
  totalRounds: number;
  psychicPlayer: Player | undefined;
  isPsychic: boolean;
}) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3">
      <span className="text-sm text-zinc-400">
        Round <span className="font-semibold text-zinc-100">{roundNumber}</span>{" "}
        / {totalRounds}
      </span>
      <span className="text-sm text-zinc-400">
        Psychic:{" "}
        <span className="font-semibold text-rose-400">
          {isPsychic ? "You" : (psychicPlayer ? `${avatarEmoji(psychicPlayer.avatar)} ${psychicPlayer.display_name}` : "—")}
        </span>
      </span>
    </div>
  );
}

// ---- Spectrum bar ----

function SpectrumBar({
  leftLabel,
  rightLabel,
  targetPosition,
  guesses,
  sliderValue,
  onSliderChange,
  readonly,
}: {
  leftLabel: string;
  rightLabel: string;
  targetPosition?: number | null;
  guesses?: Record<string, number> | null;
  sliderValue?: number;
  onSliderChange?: (value: number) => void;
  readonly?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="relative h-10 rounded-full bg-gradient-to-r from-blue-700 via-purple-600 to-rose-500">
        {/* Target marker (psychic only, or at reveal) */}
        {targetPosition != null && (
          <div
            className="absolute top-0 flex h-10 -translate-x-1/2 flex-col items-center"
            style={{ left: `${targetPosition}%` }}
          >
            <div className="h-full w-1 bg-yellow-400 opacity-90" />
            <span className="mt-1 rounded bg-yellow-400 px-1 text-xs font-bold text-yellow-900">
              Target
            </span>
          </div>
        )}

        {/* Guesses at reveal */}
        {guesses &&
          Object.entries(guesses).map(([pid, pos]) => (
            <div
              key={pid}
              className="absolute top-0 flex h-10 -translate-x-1/2 items-center"
              style={{ left: `${pos}%` }}
              title={`${pid}: ${pos.toFixed(1)}`}
            >
              <div className="h-full w-0.5 bg-white opacity-70" />
            </div>
          ))}
      </div>

      {/* Slider for guessers */}
      {!readonly && onSliderChange !== undefined && (
        <input
          type="range"
          min={0}
          max={100}
          step={0.5}
          value={sliderValue ?? 50}
          onChange={(e: ChangeEvent<HTMLInputElement>) => onSliderChange(Number(e.target.value))}
          className="w-full accent-rose-500"
          aria-label="Spectrum position"
        />
      )}

      <div className="flex justify-between text-xs font-semibold text-zinc-300">
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>
    </div>
  );
}

// ---- Clue-giving phase ----

function ClueGivingPhase({
  isPsychic,
  psychicSecret,
  leftLabel,
  rightLabel,
  onGiveClue,
}: {
  isPsychic: boolean;
  psychicSecret: number | null;
  leftLabel: string;
  rightLabel: string;
  onGiveClue: (clueText: string) => void;
}) {
  const [clueText, setClueText] = useState("");

  if (isPsychic) {
    return (
      <div className="flex flex-col gap-4 rounded-xl border border-rose-900 bg-rose-950/20 p-5">
        <p className="text-center text-sm font-semibold text-rose-300">
          You are the Psychic this round.
        </p>

        <SpectrumBar
          leftLabel={leftLabel}
          rightLabel={rightLabel}
          targetPosition={psychicSecret}
          readonly
        />

        {psychicSecret != null && (
          <p className="text-center text-xs text-zinc-400">
            Target is at{" "}
            <span className="font-semibold text-yellow-400">{psychicSecret.toFixed(1)}</span> on the
            spectrum. Give a one-word clue out loud!
          </p>
        )}

        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            value={clueText}
            onChange={(e) => setClueText(e.target.value)}
            placeholder="Optional: type your clue for all to see"
            maxLength={40}
            className="h-10 flex-1 rounded-full border border-zinc-700 bg-zinc-950 px-4 text-sm text-zinc-50 outline-none focus:border-rose-500"
          />
          <button
            type="button"
            onClick={() => onGiveClue(clueText.trim())}
            className="h-10 rounded-full bg-rose-500 px-6 text-sm font-medium text-white transition-colors hover:bg-rose-400"
          >
            Start guessing
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <p className="text-center text-sm text-zinc-400">
        Waiting for the Psychic to give a clue…
      </p>
      <SpectrumBar leftLabel={leftLabel} rightLabel={rightLabel} readonly />
    </div>
  );
}

// ---- Guessing phase ----

function GuessingPhase({
  isPsychic,
  leftLabel,
  rightLabel,
  clueText,
  guessedCount,
  totalGuessers,
  onSubmitGuess,
  onForceReveal,
}: {
  isPsychic: boolean;
  leftLabel: string;
  rightLabel: string;
  clueText: string | null;
  guessedCount: number;
  totalGuessers: number;
  onSubmitGuess: (position: number) => void;
  onForceReveal: () => void;
}) {
  const [sliderValue, setSliderValue] = useState(50);
  const [locked, setLocked] = useState(false);

  function handleLock() {
    onSubmitGuess(sliderValue);
    setLocked(true);
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      {clueText && (
        <p className="text-center text-sm text-zinc-300">
          Clue:{" "}
          <span className="font-semibold text-zinc-50">&ldquo;{clueText}&rdquo;</span>
        </p>
      )}

      <p className="text-center text-xs text-zinc-500">
        {guessedCount} / {totalGuessers} guessers locked in
      </p>

      {isPsychic ? (
        <div className="flex flex-col items-center gap-3">
          <SpectrumBar leftLabel={leftLabel} rightLabel={rightLabel} readonly />
          <p className="text-center text-sm text-zinc-500">
            Guessers are choosing their positions.
          </p>
          <button
            type="button"
            onClick={onForceReveal}
            className="h-10 rounded-full border border-zinc-700 px-6 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500"
          >
            Force reveal
          </button>
        </div>
      ) : locked ? (
        <div className="flex flex-col gap-3">
          <SpectrumBar
            leftLabel={leftLabel}
            rightLabel={rightLabel}
            sliderValue={sliderValue}
            readonly
          />
          <p className="text-center text-sm text-emerald-400">
            Locked in at {sliderValue.toFixed(1)} — waiting for others.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <SpectrumBar
            leftLabel={leftLabel}
            rightLabel={rightLabel}
            sliderValue={sliderValue}
            onSliderChange={setSliderValue}
          />
          <p className="text-center text-sm text-zinc-400">
            Your guess: <span className="font-semibold text-zinc-100">{sliderValue.toFixed(1)}</span>
          </p>
          <button
            type="button"
            onClick={handleLock}
            className="h-10 rounded-full bg-rose-500 px-6 text-sm font-medium text-white transition-colors hover:bg-rose-400"
          >
            Lock in
          </button>
        </div>
      )}
    </div>
  );
}

// ---- Reveal phase ----

function RevealPhase({
  leftLabel,
  rightLabel,
  targetPosition,
  guesses,
  pointsAwarded,
  scores,
  players,
  playerById,
  onNextRound,
}: {
  leftLabel: string;
  rightLabel: string;
  targetPosition: number | null;
  guesses: Record<string, number> | null;
  pointsAwarded: Record<string, number> | null;
  scores: Record<string, number>;
  players: Player[];
  playerById: Record<string, Player>;
  onNextRound: () => void;
}) {
  return (
    <div className="flex flex-col gap-5 rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <h2 className="text-center text-sm font-semibold text-zinc-300">Reveal</h2>

      <SpectrumBar
        leftLabel={leftLabel}
        rightLabel={rightLabel}
        targetPosition={targetPosition}
        guesses={guesses}
        readonly
      />

      {guesses && pointsAwarded && (
        <ul className="flex flex-col gap-1">
          {Object.entries(guesses)
            .sort(([, a], [, b]) => (pointsAwarded[b] ?? 0) - (pointsAwarded[a] ?? 0))
            .map(([pid, pos]) => {
              const player = playerById[pid];
              const pts = pointsAwarded[pid] ?? 0;
              const dist = targetPosition != null ? Math.abs(pos - targetPosition).toFixed(1) : "—";
              return (
                <li key={pid} className="flex items-center justify-between rounded-lg px-3 py-1.5">
                  <span className="text-sm">
                    {player ? `${avatarEmoji(player.avatar)} ${player.display_name}` : pid}
                  </span>
                  <span className="text-sm">
                    <span className="text-zinc-400">{pos.toFixed(1)}</span>{" "}
                    <span className="text-zinc-600">(Δ {dist})</span>{" "}
                    <span className="font-semibold text-rose-400">+{pts}</span>
                  </span>
                </li>
              );
            })}
        </ul>
      )}

      <button
        type="button"
        onClick={onNextRound}
        className="h-10 rounded-full bg-rose-500 px-6 text-sm font-medium text-white transition-colors hover:bg-rose-400"
      >
        Next round
      </button>
    </div>
  );
}

// ---- Game over ----

function GameOverScreen({
  scores,
  players,
  onHome,
}: {
  scores: Record<string, number>;
  players: Player[];
  onHome: () => void;
}) {
  const sorted = [...players]
    .filter((p) => !p.is_spectator)
    .sort((a, b) => (scores[b.id] ?? 0) - (scores[a.id] ?? 0));

  const winner = sorted[0];

  return (
    <div className="flex flex-col items-center gap-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
      <span className="rounded-full border border-zinc-800 bg-zinc-950 px-4 py-1 text-sm font-medium text-zinc-400">
        Game over
      </span>
      {winner && (
        <h2 className="text-2xl font-semibold tracking-tight">
          <span className="text-rose-400">{avatarEmoji(winner.avatar)} {winner.display_name}</span>{" "}
          wins!
        </h2>
      )}

      <ol className="flex w-full flex-col gap-2">
        {sorted.map((player, rank) => (
          <li key={player.id} className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-2">
            <span className="flex items-center gap-2 text-sm font-medium">
              <span className="w-5 text-zinc-500">#{rank + 1}</span>
              <span>{avatarEmoji(player.avatar)}</span>
              <span>{player.display_name}</span>
            </span>
            <span className="text-sm font-semibold text-rose-400">{scores[player.id] ?? 0} pts</span>
          </li>
        ))}
      </ol>

      <button
        type="button"
        onClick={onHome}
        className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400"
      >
        Back home
      </button>
    </div>
  );
}

// ---- Leaderboard (shown during active rounds) ----

function Leaderboard({
  scores,
  players,
}: {
  scores: Record<string, number>;
  players: Player[];
}) {
  const sorted = [...players]
    .filter((p) => !p.is_spectator)
    .sort((a, b) => (scores[b.id] ?? 0) - (scores[a.id] ?? 0));

  if (sorted.every((p) => (scores[p.id] ?? 0) === 0)) return null;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">Scores</h3>
      <ol className="flex flex-col gap-1">
        {sorted.map((player, rank) => (
          <li key={player.id} className="flex items-center justify-between px-1">
            <span className="flex items-center gap-2 text-sm">
              <span className="w-4 text-zinc-600">#{rank + 1}</span>
              <span>{avatarEmoji(player.avatar)}</span>
              <span className="text-zinc-200">{player.display_name}</span>
            </span>
            <span className="text-sm font-semibold text-rose-400">{scores[player.id] ?? 0}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
