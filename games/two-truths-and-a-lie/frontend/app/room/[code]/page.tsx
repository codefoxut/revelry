"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import { useRoomStore } from "@/store/roomStore";
import { joinRoom } from "@/services/api";
import { clearPlayerId, loadPlayerId, savePlayerId } from "@/lib/session";
import { LobbyView } from "@/features/room/LobbyView";
import { AvatarPicker } from "@/components/AvatarPicker";
import { Spinner } from "@/components/Spinner";
import { AVATARS } from "@/lib/avatars";

const ROOM_OR_PLAYER_NOT_FOUND = 4404;

export default function RoomPage() {
  const params = useParams<{ code: string }>();
  const roomCode = (params.code ?? "").toUpperCase();

  const status = useRoomStore((state) => state.status);
  const closeCode = useRoomStore((state) => state.closeCode);
  const connect = useRoomStore((state) => state.connect);
  const disconnect = useRoomStore((state) => state.disconnect);

  const [needsName, setNeedsName] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [avatar, setAvatar] = useState<string>(AVATARS[0].key);
  const [joinError, setJoinError] = useState<string | null>(null);
  const [isJoining, setIsJoining] = useState(false);

  useEffect(() => {
    const existingPlayerId = loadPlayerId(roomCode);
    if (existingPlayerId) {
      connect(roomCode, existingPlayerId);
    } else {
      // One-time branch on sessionStorage (an external system), not state derivable during render.
      setNeedsName(true); // eslint-disable-line react-hooks/set-state-in-effect
    }
    return () => disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roomCode]);

  useEffect(() => {
    if (status === "closed" && closeCode === ROOM_OR_PLAYER_NOT_FOUND) {
      clearPlayerId(roomCode);
      // Reacting to the socket's close code, not state derivable during render.
      setNeedsName(true); // eslint-disable-line react-hooks/set-state-in-effect
    }
  }, [status, closeCode, roomCode]);

  async function handleJoin(event: FormEvent) {
    event.preventDefault();
    if (!displayName.trim()) return;

    setIsJoining(true);
    setJoinError(null);
    try {
      const { room, player_id } = await joinRoom(roomCode, displayName.trim(), avatar);
      savePlayerId(room.code, player_id);
      setNeedsName(false);
      connect(room.code, player_id);
    } catch (err) {
      setJoinError(err instanceof Error ? err.message : "Could not join that room");
    } finally {
      setIsJoining(false);
    }
  }

  if (needsName) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center bg-zinc-950 px-6 py-24 text-zinc-50">
        <form onSubmit={handleJoin} className="flex w-full max-w-xs flex-col gap-3 text-center">
          <h1 className="mb-2 text-2xl font-semibold tracking-tight">
            Join room <span className="text-rose-500">{roomCode}</span>
          </h1>
          <input
            autoFocus
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Your name"
            maxLength={24}
            className="h-12 rounded-full border border-zinc-700 bg-zinc-900 px-5 text-center text-zinc-50 outline-none focus:border-rose-500"
          />
          <AvatarPicker value={avatar} onChange={setAvatar} />
          {joinError && (
            <p role="alert" className="text-sm text-rose-400">
              {joinError}
            </p>
          )}
          <button
            type="submit"
            disabled={isJoining || !displayName.trim()}
            className="flex h-12 items-center justify-center gap-2 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isJoining && <Spinner />}
            {isJoining ? "Joining…" : "Join Room"}
          </button>
        </form>
      </div>
    );
  }

  return <LobbyView />;
}
