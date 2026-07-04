"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRoomStore } from "@/store/roomStore";
import { clearPlayerId } from "@/lib/session";
import type { Player } from "@/types/room";

// Mirrors MAFIA_MODULE.min_players in app/games/mafia/__init__.py.
const MIN_PLAYERS_TO_START = 4;

export function LobbyView() {
  const router = useRouter();
  const room = useRoomStore((state) => state.room);
  const selfPlayerId = useRoomStore((state) => state.selfPlayerId);
  const myRole = useRoomStore((state) => state.myRole);
  const status = useRoomStore((state) => state.status);
  const kicked = useRoomStore((state) => state.kicked);
  const lastError = useRoomStore((state) => state.lastError);
  const sendCommand = useRoomStore((state) => state.sendCommand);
  const disconnect = useRoomStore((state) => state.disconnect);
  const [copied, setCopied] = useState(false);

  if (kicked) {
    return (
      <Centered>
        <p className="text-lg text-zinc-200">
          You were removed from this room by the host.
        </p>
        <button
          type="button"
          onClick={() => router.push("/")}
          className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400"
        >
          Back home
        </button>
      </Centered>
    );
  }

  if (!room) {
    return (
      <Centered>
        <p className="text-zinc-400">
          {status === "closed" ? "Couldn't connect to that room." : "Connecting…"}
        </p>
      </Centered>
    );
  }

  const self = room.players.find((player) => player.id === selfPlayerId);
  const isHost = self?.is_host ?? false;
  const activePlayerCount = room.players.filter((player) => !player.is_spectator).length;
  const inGame = room.phase === "in_game";

  function toggleReady() {
    sendCommand({ type: "set_ready", ready: !self?.is_ready });
  }

  function kick(targetId: string) {
    sendCommand({ type: "kick_player", target_player_id: targetId });
  }

  function startGame() {
    sendCommand({ type: "start_game" });
  }

  function advancePhase() {
    sendCommand({ type: "advance_phase" });
  }

  function leave() {
    sendCommand({ type: "leave_room" });
    clearPlayerId(room!.code);
    disconnect();
    router.push("/");
  }

  async function copyInvite() {
    await navigator.clipboard.writeText(room!.invite_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-950 px-6 py-16 text-zinc-50">
      <div className="flex w-full max-w-lg flex-col gap-6">
        <header className="flex flex-col items-center gap-2 text-center">
          <span className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-1 text-sm font-medium text-zinc-400">
            Lobby
          </span>
          <h1 className="text-3xl font-semibold tracking-tight">
            Room <span className="text-rose-500">{room.code}</span>
          </h1>
          <button
            type="button"
            onClick={copyInvite}
            className="text-sm text-zinc-400 underline decoration-dotted underline-offset-4 hover:text-zinc-200"
          >
            {copied ? "Copied!" : "Copy invite link"}
          </button>
        </header>

        {lastError && (
          <p className="rounded-lg border border-rose-900 bg-rose-950/50 px-4 py-2 text-center text-sm text-rose-300">
            {lastError.message}
          </p>
        )}

        <ul className="flex flex-col gap-2 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
          {room.players.map((player) => (
            <PlayerRow
              key={player.id}
              player={player}
              isSelf={player.id === selfPlayerId}
              canKick={isHost && player.id !== selfPlayerId}
              onKick={() => kick(player.id)}
            />
          ))}
        </ul>

        <p className="text-center text-sm text-zinc-500">
          {room.players.length} / {room.max_players} players &middot;{" "}
          {room.players.filter((p) => p.is_ready).length} ready
        </p>

        {inGame && myRole && (
          <div className="flex flex-col items-center gap-1 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
            <span className="text-xs uppercase tracking-wide text-zinc-500">Your role</span>
            <span className="text-xl font-semibold text-rose-400">{myRole.display_name}</span>
            <span className="text-xs uppercase tracking-wide text-zinc-600">{myRole.team} team</span>
            <p className="mt-1 text-center text-sm text-zinc-400">{myRole.description}</p>
          </div>
        )}

        {inGame && room.game_state && (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
            <span className="rounded-full border border-rose-900 bg-rose-950/50 px-4 py-1 text-sm font-medium capitalize text-rose-300">
              {room.game_state.phase} &middot; Round {room.game_state.round_number}
            </span>
            <p className="text-center text-sm text-zinc-500">
              Night actions and voting are coming up next — for now the host can
              step through phases manually.
            </p>
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
        )}

        {!inGame && (
          <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
            <button
              type="button"
              onClick={toggleReady}
              className={`h-12 rounded-full px-8 font-medium transition-colors ${
                self?.is_ready
                  ? "border border-zinc-700 text-zinc-200 hover:border-zinc-500"
                  : "bg-rose-500 text-white hover:bg-rose-400"
              }`}
            >
              {self?.is_ready ? "Not ready" : "Ready"}
            </button>
            <button
              type="button"
              onClick={leave}
              className="h-12 rounded-full border border-zinc-700 px-8 font-medium text-zinc-400 transition-colors hover:border-zinc-500 hover:text-zinc-200"
            >
              Leave room
            </button>
          </div>
        )}

        {!inGame && isHost && (
          <div className="flex flex-col items-center gap-2">
            <button
              type="button"
              onClick={startGame}
              disabled={activePlayerCount < MIN_PLAYERS_TO_START}
              className="h-12 rounded-full bg-rose-500 px-8 font-medium text-white transition-colors hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Start game
            </button>
            {activePlayerCount < MIN_PLAYERS_TO_START && (
              <p className="text-sm text-zinc-600">
                Need at least {MIN_PLAYERS_TO_START} players to start ({activePlayerCount} so far).
              </p>
            )}
          </div>
        )}

        {!inGame && !isHost && (
          <p className="text-center text-sm text-zinc-600">
            Waiting for the host to start the game.
          </p>
        )}
      </div>
    </div>
  );
}

function PlayerRow({
  player,
  isSelf,
  canKick,
  onKick,
}: {
  player: Player;
  isSelf: boolean;
  canKick: boolean;
  onKick: () => void;
}) {
  return (
    <li className="flex items-center justify-between rounded-lg px-3 py-2">
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${player.connected ? "bg-emerald-500" : "bg-zinc-600"}`} />
        <span className="font-medium">
          {player.display_name}
          {isSelf && <span className="text-zinc-500"> (you)</span>}
        </span>
        {player.is_host && (
          <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">Host</span>
        )}
        {player.is_spectator && (
          <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">Spectator</span>
        )}
      </div>
      <div className="flex items-center gap-3">
        {player.is_ready && <span className="text-sm text-emerald-400">Ready</span>}
        {canKick && (
          <button
            type="button"
            onClick={onKick}
            className="text-sm text-zinc-500 hover:text-rose-400"
          >
            Kick
          </button>
        )}
      </div>
    </li>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 bg-zinc-950 px-6 py-24 text-zinc-50">
      {children}
    </div>
  );
}
