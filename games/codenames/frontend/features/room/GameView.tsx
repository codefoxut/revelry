"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useRoomStore } from "@/store/roomStore";
import type { BoardCard } from "@/types/room";

// "assassin" describes the team that guessed it (the loser); "all_words_found"
// describes the team that finished their board (the winner) — so the subject
// of each sentence isn't always the winning side.
const REASON_TEXT: Record<string, { subject: "winner" | "loser"; text: string }> = {
  assassin: { subject: "loser", text: "guessed the assassin card." },
  all_words_found: { subject: "winner", text: "found every one of their words." },
};

export function GameView() {
  const router = useRouter();
  const room = useRoomStore((state) => state.room);
  const myAssignment = useRoomStore((state) => state.myAssignment);
  const spymasterColors = useRoomStore((state) => state.spymasterColors);
  const gameOver = useRoomStore((state) => state.gameOver);
  const lastError = useRoomStore((state) => state.lastError);
  const sendCommand = useRoomStore((state) => state.sendCommand);

  const gameState = room?.game_state;

  if (!room || !gameState) return null;

  const myTeam = myAssignment?.team ?? null;
  const isSpymaster = myAssignment?.role === "spymaster";
  const isMyTurn = gameState.current_team === myTeam;

  function giveClue(word: string, number: number) {
    sendCommand({ type: "give_clue", word, number });
  }

  function makeGuess(cardIndex: number) {
    sendCommand({ type: "make_guess", card_index: cardIndex });
  }

  function endTurn() {
    sendCommand({ type: "end_turn" });
  }

  if (gameOver) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-6 bg-zinc-950 px-6 py-16 text-zinc-50">
        <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-1 text-sm font-medium text-zinc-400">
          Game over
        </span>
        <h1 className="text-3xl font-semibold capitalize tracking-tight">
          <span className={gameOver.winningSide === "red" ? "text-red-400" : "text-blue-400"}>
            {gameOver.winningSide}
          </span>{" "}
          wins
        </h1>
        <p className="text-center text-sm capitalize text-zinc-400">
          {(() => {
            const reasonInfo = REASON_TEXT[gameOver.reason];
            const losingSide = gameOver.winningSide === "red" ? "blue" : "red";
            const subjectTeam = reasonInfo?.subject === "loser" ? losingSide : gameOver.winningSide;
            return `${subjectTeam} ${reasonInfo?.text ?? gameOver.reason}`;
          })()}
        </p>

        <BoardGrid
          board={gameState.board}
          revealOverrides={gameOver.colors}
          onCardClick={undefined}
        />

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
      {myAssignment && (
        <div className="flex flex-col items-center gap-1 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
          <span className="text-xs uppercase tracking-wide text-zinc-500">Your team</span>
          <span
            className={`text-xl font-semibold capitalize ${
              myTeam === "red" ? "text-red-400" : "text-blue-400"
            }`}
          >
            {myTeam}
          </span>
          <span className="text-xs uppercase tracking-wide text-zinc-600">
            {isSpymaster ? "Spymaster" : "Guesser"}
          </span>
        </div>
      )}

      <div className="flex flex-col items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
        <div className="flex w-full items-center justify-between text-sm">
          <span className="font-medium text-red-400">Red: {gameState.red_remaining}</span>
          <span
            className={`rounded-full border px-4 py-1 text-sm font-medium capitalize ${
              gameState.current_team === "red"
                ? "border-red-900 bg-red-950/50 text-red-300"
                : "border-blue-900 bg-blue-950/50 text-blue-300"
            }`}
          >
            {gameState.current_team}&rsquo;s turn
          </span>
          <span className="font-medium text-blue-400">Blue: {gameState.blue_remaining}</span>
        </div>

        {gameState.current_clue && (
          <p className="text-center text-sm text-zinc-300">
            Clue: <span className="font-semibold text-zinc-50">{gameState.current_clue.word}</span>{" "}
            &middot; {gameState.current_clue.number}{" "}
            <span className="text-zinc-500">
              ({gameState.current_clue.guesses_made}/{gameState.current_clue.max_guesses} guesses used)
            </span>
          </p>
        )}

        {lastError && (
          <p role="alert" className="text-center text-sm text-rose-400">
            {lastError.message}
          </p>
        )}

        {isMyTurn && isSpymaster && !gameState.current_clue && (
          <ClueForm onSubmit={giveClue} />
        )}

        {isMyTurn && !isSpymaster && gameState.current_clue && (
          <button
            type="button"
            onClick={endTurn}
            className="h-10 rounded-full border border-zinc-700 px-6 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500"
          >
            End turn
          </button>
        )}

        {!isMyTurn && (
          <p className="text-center text-sm text-zinc-600">
            Waiting for {gameState.current_team}&rsquo;s{" "}
            {gameState.current_clue ? "guessers" : "spymaster"}.
          </p>
        )}
      </div>

      <BoardGrid
        board={gameState.board}
        spymasterColors={isSpymaster ? spymasterColors : null}
        onCardClick={
          isMyTurn && !isSpymaster && gameState.current_clue ? makeGuess : undefined
        }
      />
    </div>
  );
}

function ClueForm({ onSubmit }: { onSubmit: (word: string, number: number) => void }) {
  const [word, setWord] = useState("");
  const [number, setNumber] = useState(1);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!word.trim()) return;
    onSubmit(word.trim(), number);
    setWord("");
    setNumber(1);
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-sm flex-col gap-2 sm:flex-row">
      <input
        autoFocus
        value={word}
        onChange={(event) => setWord(event.target.value)}
        placeholder="Your clue word"
        maxLength={40}
        className="h-10 flex-1 rounded-full border border-zinc-700 bg-zinc-950 px-4 text-sm text-zinc-50 outline-none focus:border-rose-500"
      />
      <select
        value={number}
        onChange={(event) => setNumber(Number(event.target.value))}
        className="h-10 rounded-full border border-zinc-700 bg-zinc-950 px-3 text-sm text-zinc-50 outline-none focus:border-rose-500"
      >
        {Array.from({ length: 10 }, (_, n) => n).map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
      <button
        type="submit"
        disabled={!word.trim()}
        className="h-10 rounded-full bg-rose-500 px-6 text-sm font-medium text-white transition-colors hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Give clue
      </button>
    </form>
  );
}

function BoardGrid({
  board,
  spymasterColors,
  revealOverrides,
  onCardClick,
}: {
  board: BoardCard[];
  spymasterColors?: string[] | null;
  revealOverrides?: string[];
  onCardClick: ((cardIndex: number) => void) | undefined;
}) {
  return (
    <div className="grid grid-cols-5 gap-1.5 sm:gap-2">
      {board.map((card, index) => {
        const finalColor = revealOverrides?.[index] ?? null;
        const isRevealed = card.revealed || finalColor !== null;
        const color = card.color ?? finalColor;
        const hint = !isRevealed ? spymasterColors?.[index] ?? null : null;
        const clickable = !isRevealed && onCardClick !== undefined;

        return (
          <button
            key={index}
            type="button"
            disabled={!clickable}
            onClick={() => onCardClick?.(index)}
            className={cardClasses(color, isRevealed, hint, clickable)}
          >
            {card.word}
          </button>
        );
      })}
    </div>
  );
}

function cardClasses(
  color: string | null,
  revealed: boolean,
  hint: string | null,
  clickable: boolean,
): string {
  const base =
    "flex aspect-[4/3] items-center justify-center rounded-lg border px-1 text-center text-[10px] font-semibold uppercase tracking-tight transition-colors sm:text-xs";

  if (revealed && color) {
    return `${base} ${REVEALED_CLASSES[color] ?? REVEALED_CLASSES.neutral} cursor-default`;
  }

  const hintClass = hint ? HINT_RING_CLASSES[hint] ?? "" : "";
  const interactive = clickable ? "hover:border-rose-500 cursor-pointer" : "cursor-default";
  return `${base} border-zinc-700 bg-zinc-800 text-zinc-100 ${hintClass} ${interactive}`;
}

const REVEALED_CLASSES: Record<string, string> = {
  red: "border-red-500 bg-red-600 text-white",
  blue: "border-blue-500 bg-blue-600 text-white",
  neutral: "border-stone-400 bg-stone-300 text-zinc-900",
  assassin: "border-black bg-zinc-950 text-white",
};

const HINT_RING_CLASSES: Record<string, string> = {
  red: "ring-2 ring-inset ring-red-500",
  blue: "ring-2 ring-inset ring-blue-500",
  neutral: "ring-2 ring-inset ring-stone-400",
  assassin: "ring-2 ring-inset ring-zinc-100",
};
