"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { createRoom, joinRoom } from "@/services/api";
import { savePlayerId } from "@/lib/session";
import { AvatarPicker } from "@/components/AvatarPicker";
import { Spinner } from "@/components/Spinner";
import { AVATARS } from "@/lib/avatars";

type Panel = "closed" | "create" | "join";

export default function Home() {
  const router = useRouter();
  const [panel, setPanel] = useState<Panel>("closed");
  const [displayName, setDisplayName] = useState("");
  const [roomCode, setRoomCode] = useState("");
  const [avatar, setAvatar] = useState<string>(AVATARS[0].key);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function openPanel(next: Panel) {
    setPanel(next);
    setError(null);
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!displayName.trim()) return;

    setIsSubmitting(true);
    setError(null);
    try {
      const { room, player_id } = await createRoom(displayName.trim(), avatar);
      savePlayerId(room.code, player_id);
      router.push(`/room/${room.code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setIsSubmitting(false);
    }
  }

  async function handleJoin(event: FormEvent) {
    event.preventDefault();
    if (!displayName.trim() || !roomCode.trim()) return;

    setIsSubmitting(true);
    setError(null);
    try {
      const code = roomCode.trim().toUpperCase();
      const { room, player_id } = await joinRoom(code, displayName.trim(), avatar);
      savePlayerId(room.code, player_id);
      router.push(`/room/${room.code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not join that room");
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-950 px-6 py-24 text-zinc-50">
      <main className="flex w-full max-w-2xl flex-col items-center gap-8 text-center">
        <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-1 text-sm font-medium text-zinc-400">
          Revelry
        </span>

        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Codenames, with your friends,{" "}
          <span className="text-rose-500">in your browser.</span>
        </h1>

        <p className="max-w-md text-lg leading-8 text-zinc-400">
          No installs, no accounts. Split into two teams, grab a room code, and have your
          spymaster steer your guessers to every one of your words before the other team — or
          the assassin — gets there first.
        </p>

        {panel === "closed" && (
          <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
            <button
              type="button"
              onClick={() => openPanel("create")}
              className="h-12 w-full rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400 sm:w-auto"
            >
              Create Room
            </button>
            <button
              type="button"
              onClick={() => openPanel("join")}
              className="h-12 w-full rounded-full border border-zinc-700 px-8 font-medium text-zinc-200 transition-colors hover:border-zinc-500 sm:w-auto"
            >
              Join with Code
            </button>
          </div>
        )}

        {panel === "create" && (
          <form
            onSubmit={handleCreate}
            className="flex w-full max-w-xs flex-col gap-3"
          >
            <input
              autoFocus
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Your name"
              maxLength={24}
              className="h-12 rounded-full border border-zinc-700 bg-zinc-900 px-5 text-center text-zinc-50 outline-none focus:border-rose-500"
            />
            <AvatarPicker value={avatar} onChange={setAvatar} />
            {error && (
              <p role="alert" className="text-sm text-rose-400">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={isSubmitting || !displayName.trim()}
              className="flex h-12 items-center justify-center gap-2 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting && <Spinner />}
              {isSubmitting ? "Creating…" : "Create Room"}
            </button>
            <button
              type="button"
              onClick={() => openPanel("closed")}
              className="text-sm text-zinc-500 hover:text-zinc-300"
            >
              Back
            </button>
          </form>
        )}

        {panel === "join" && (
          <form onSubmit={handleJoin} className="flex w-full max-w-xs flex-col gap-3">
            <input
              autoFocus
              value={roomCode}
              onChange={(event) => setRoomCode(event.target.value)}
              placeholder="Room code"
              maxLength={5}
              className="h-12 rounded-full border border-zinc-700 bg-zinc-900 px-5 text-center uppercase tracking-widest text-zinc-50 outline-none focus:border-rose-500"
            />
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Your name"
              maxLength={24}
              className="h-12 rounded-full border border-zinc-700 bg-zinc-900 px-5 text-center text-zinc-50 outline-none focus:border-rose-500"
            />
            <AvatarPicker value={avatar} onChange={setAvatar} />
            {error && (
              <p role="alert" className="text-sm text-rose-400">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={isSubmitting || !displayName.trim() || !roomCode.trim()}
              className="flex h-12 items-center justify-center gap-2 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting && <Spinner />}
              {isSubmitting ? "Joining…" : "Join Room"}
            </button>
            <button
              type="button"
              onClick={() => openPanel("closed")}
              className="text-sm text-zinc-500 hover:text-zinc-300"
            >
              Back
            </button>
          </form>
        )}
      </main>

      <section className="mt-20 flex w-full max-w-3xl flex-col gap-10">
        <div className="flex flex-col items-center gap-2 text-center">
          <h2 className="text-2xl font-semibold tracking-tight">How a round works</h2>
          <p className="max-w-xl text-zinc-400">
            Starting a game deals a shared 25-word board and splits the room into a red team and a
            blue team, each with one secret spymaster. On your team&rsquo;s turn, your{" "}
            <strong className="text-zinc-200">spymaster</strong> gives a one-word clue plus a
            number, and your <strong className="text-zinc-200">guessers</strong> click cards
            trying to find your team&rsquo;s words. Guess right and keep going, guess wrong and
            the turn passes — guess the black assassin card and your team loses instantly. First
            team to find all of their words wins.
          </p>
        </div>

        <div className="flex flex-col items-center gap-2 text-center">
          <h2 className="text-2xl font-semibold tracking-tight">Play in person</h2>
          <p className="max-w-xl text-zinc-400">
            Everyone plays from their own phone or laptop — spymasters see the full color key on
            their own screen, guessers only see what&rsquo;s been revealed. Gather around and talk
            it out out loud; there&rsquo;s no in-app chat needed.
          </p>
        </div>
      </section>
    </div>
  );
}
