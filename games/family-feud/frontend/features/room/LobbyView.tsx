"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRoomStore } from "@/store/roomStore";
import { clearPlayerId } from "@/lib/session";
import { GameView } from "./GameView";
import { avatarEmoji } from "@/lib/avatars";
import type { Player } from "@/types/room";

const MIN_PLAYERS_TO_START = 2;

export function LobbyView() {
  const router = useRouter();
  const room = useRoomStore((state) => state.room);
  const selfPlayerId = useRoomStore((state) => state.selfPlayerId);
  const status = useRoomStore((state) => state.status);
  const kicked = useRoomStore((state) => state.kicked);
  const lastError = useRoomStore((state) => state.lastError);
  const sendCommand = useRoomStore((state) => state.sendCommand);
  const disconnect = useRoomStore((state) => state.disconnect);
  const [copied, setCopied] = useState(false);

  if (kicked) {
    return (
      <Centered>
        <p className="text-lg text-zinc-200">You were removed from this room by the host.</p>
        <button
          type="button"
          onClick={() => router.push("/")}
          className="h-12 rounded-full bg-amber-500 px-8 font-medium text-zinc-950 transition-colors hover:bg-amber-400"
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
  const inGame = room.phase === "in_game";

  const teamOf: Record<string, "a" | "b"> =
    (room.game_state?.team_of as Record<string, "a" | "b">) ?? {};
  const myTeam = selfPlayerId ? teamOf[selfPlayerId] : undefined;

  const teamA = room.players.filter((p) => teamOf[p.id] === "a");
  const teamB = room.players.filter((p) => teamOf[p.id] === "b");
  const unassigned = room.players.filter((p) => !teamOf[p.id] && !p.is_host);

  const canStart =
    room.players.filter((p) => !p.is_host).length >= MIN_PLAYERS_TO_START &&
    teamA.length >= 1 &&
    teamB.length >= 1;

  function joinTeam(team: "a" | "b") {
    sendCommand({ type: "join_team", team });
  }

  function startGame() {
    sendCommand({ type: "start_game" });
  }

  function leave() {
    sendCommand({ type: "leave_room" });
    clearPlayerId(room!.code);
    disconnect();
    router.push("/");
  }

  function kick(targetId: string) {
    sendCommand({ type: "kick_player", target_player_id: targetId });
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
            {inGame ? "Game" : "Lobby"}
          </span>
          <h1 className="text-3xl font-semibold tracking-tight">
            Room <span className="text-amber-500">{room.code}</span>
          </h1>
          {!inGame && (
            <button
              type="button"
              onClick={copyInvite}
              className="text-sm text-zinc-400 underline decoration-dotted underline-offset-4 hover:text-zinc-200"
            >
              {copied ? "Copied!" : "Copy invite link"}
            </button>
          )}
        </header>

        {status === "reconnecting" && (
          <p
            role="status"
            aria-live="polite"
            className="rounded-lg border border-amber-900 bg-amber-950/50 px-4 py-2 text-center text-sm text-amber-300"
          >
            Connection lost — reconnecting…
          </p>
        )}

        {lastError && (
          <p
            role="alert"
            aria-live="assertive"
            className="rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-center text-sm text-red-300"
          >
            {lastError.message}
          </p>
        )}

        {inGame ? (
          <GameView />
        ) : (
          <>
            {/* Team picker — not shown to the host */}
            {!isHost && (
              <div className="flex flex-col gap-3">
                <p className="text-center text-sm font-medium text-zinc-400">Pick your team</p>
                <div className="grid grid-cols-2 gap-3">
                  <TeamColumn
                    label="Team A"
                    color="blue"
                    players={teamA}
                    selfPlayerId={selfPlayerId}
                    isHost={isHost}
                    canKick={isHost}
                    onKick={kick}
                    active={myTeam === "a"}
                    onJoin={() => joinTeam("a")}
                  />
                  <TeamColumn
                    label="Team B"
                    color="red"
                    players={teamB}
                    selfPlayerId={selfPlayerId}
                    isHost={isHost}
                    canKick={isHost}
                    onKick={kick}
                    active={myTeam === "b"}
                    onJoin={() => joinTeam("b")}
                  />
                </div>
                {unassigned.length > 0 && (
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-3">
                    <p className="mb-2 text-xs font-medium text-zinc-500">Not assigned</p>
                    <ul className="flex flex-col gap-1">
                      {unassigned.map((p) => (
                        <PlayerRow
                          key={p.id}
                          player={p}
                          isSelf={p.id === selfPlayerId}
                          canKick={isHost && p.id !== selfPlayerId}
                          onKick={() => kick(p.id)}
                        />
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Host sees both teams without the join buttons */}
            {isHost && (
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-2 gap-3">
                  <TeamColumn
                    label="Team A"
                    color="blue"
                    players={teamA}
                    selfPlayerId={selfPlayerId}
                    isHost={isHost}
                    canKick={isHost}
                    onKick={kick}
                    active={false}
                    onJoin={undefined}
                  />
                  <TeamColumn
                    label="Team B"
                    color="red"
                    players={teamB}
                    selfPlayerId={selfPlayerId}
                    isHost={isHost}
                    canKick={isHost}
                    onKick={kick}
                    active={false}
                    onJoin={undefined}
                  />
                </div>
                {unassigned.length > 0 && (
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-3">
                    <p className="mb-2 text-xs font-medium text-zinc-500">Not yet on a team</p>
                    <ul className="flex flex-col gap-1">
                      {unassigned.map((p) => (
                        <PlayerRow
                          key={p.id}
                          player={p}
                          isSelf={false}
                          canKick
                          onKick={() => kick(p.id)}
                        />
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            <p className="text-center text-sm text-zinc-500">
              {room.players.length} / {room.max_players} players
            </p>

            <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
              <button
                type="button"
                onClick={leave}
                className="h-12 rounded-full border border-zinc-700 px-8 font-medium text-zinc-400 transition-colors hover:border-zinc-500 hover:text-zinc-200"
              >
                Leave room
              </button>
            </div>

            {isHost && (
              <div className="flex flex-col items-center gap-2">
                <button
                  type="button"
                  onClick={startGame}
                  disabled={!canStart}
                  className="h-12 rounded-full bg-amber-500 px-8 font-medium text-zinc-950 transition-colors hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Start game
                </button>
                {!canStart && (
                  <p className="text-center text-sm text-zinc-600">
                    Need at least 1 player per team to start.
                  </p>
                )}
              </div>
            )}

            {!isHost && (
              <p className="text-center text-sm text-zinc-600">
                Waiting for the host to start the game.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function TeamColumn({
  label,
  color,
  players,
  selfPlayerId,
  isHost,
  canKick,
  onKick,
  active,
  onJoin,
}: {
  label: string;
  color: "blue" | "red";
  players: Player[];
  selfPlayerId: string | null;
  isHost: boolean;
  canKick: boolean;
  onKick: (id: string) => void;
  active: boolean;
  onJoin: (() => void) | undefined;
}) {
  const accent = color === "blue" ? "border-blue-600 bg-blue-950/30" : "border-red-600 bg-red-950/30";
  const labelColor = color === "blue" ? "text-blue-400" : "text-red-400";
  const buttonCls =
    color === "blue"
      ? "bg-blue-600 text-white hover:bg-blue-500"
      : "bg-red-600 text-white hover:bg-red-500";

  return (
    <div className={`flex flex-col gap-2 rounded-xl border p-3 ${accent}`}>
      <p className={`text-center text-sm font-semibold ${labelColor}`}>{label}</p>
      <ul className="flex flex-col gap-1 min-h-[2rem]">
        {players.map((p) => (
          <PlayerRow
            key={p.id}
            player={p}
            isSelf={p.id === selfPlayerId}
            canKick={canKick && p.id !== selfPlayerId}
            onKick={() => onKick(p.id)}
          />
        ))}
        {players.length === 0 && (
          <li className="text-center text-xs text-zinc-600">empty</li>
        )}
      </ul>
      {!isHost && onJoin && !active && (
        <button
          type="button"
          onClick={onJoin}
          className={`mt-1 h-8 rounded-full text-sm font-medium transition-colors ${buttonCls}`}
        >
          Join
        </button>
      )}
      {active && (
        <span className="mt-1 text-center text-xs font-medium text-zinc-400">✓ Your team</span>
      )}
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
    <li className="flex items-center justify-between rounded-lg px-2 py-1">
      <div className="flex items-center gap-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${player.connected ? "bg-emerald-500" : "bg-zinc-600"}`} />
        <span aria-hidden="true" className="text-sm">{avatarEmoji(player.avatar)}</span>
        <span className="text-sm font-medium">
          {player.display_name}
          {isSelf && <span className="text-zinc-500"> (you)</span>}
        </span>
      </div>
      {canKick && (
        <button
          type="button"
          onClick={onKick}
          className="text-xs text-zinc-600 hover:text-red-400"
        >
          kick
        </button>
      )}
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
