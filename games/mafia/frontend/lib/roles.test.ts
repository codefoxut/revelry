import { describe, expect, it } from "vitest";
import { clampMafiaCount, isRoleAvailable, mafiaCountBounds } from "./roles";

describe("mafiaCountBounds", () => {
  it("matches the good-gameplay table at representative counts", () => {
    expect(mafiaCountBounds(4)).toEqual({ min: 1, max: 1, default: 1 });
    expect(mafiaCountBounds(8)).toEqual({ min: 1, max: 2, default: 2 });
    expect(mafiaCountBounds(9)).toEqual({ min: 1, max: 3, default: 2 });
    expect(mafiaCountBounds(12)).toEqual({ min: 1, max: 4, default: 3 });
    expect(mafiaCountBounds(20)).toEqual({ min: 1, max: 6, default: 5 });
  });

  it("clamps out-of-range counts to the table's edges", () => {
    expect(mafiaCountBounds(2)).toEqual(mafiaCountBounds(4));
    expect(mafiaCountBounds(100)).toEqual(mafiaCountBounds(20));
  });
});

describe("clampMafiaCount", () => {
  it("defaults to the table's default when no count is requested", () => {
    expect(clampMafiaCount(4, null)).toBe(1);
    expect(clampMafiaCount(8, null)).toBe(2);
    expect(clampMafiaCount(12, null)).toBe(3);
  });

  it("enforces at least the table minimum", () => {
    expect(clampMafiaCount(4, 0)).toBe(1);
    expect(clampMafiaCount(4, -5)).toBe(1);
  });

  it("never exceeds the table maximum", () => {
    expect(clampMafiaCount(6, 100)).toBe(2);
  });

  it("respects a valid in-range request", () => {
    expect(clampMafiaCount(12, 3)).toBe(3);
  });
});

describe("isRoleAvailable", () => {
  it("rejects a role that would overflow the remaining slots", () => {
    expect(isRoleAvailable("doctor", 3, 1, ["detective", "bodyguard"])).toBe(false);
  });

  it("allows a role that fits within remaining slots", () => {
    expect(isRoleAvailable("doctor", 6, 1, ["detective"])).toBe(true);
  });

  it("rejects terrorist when it would create instant mafia win-parity", () => {
    // 6 players, 2 mafia: mafia_alive = 2 + 1 = 3, town_alive = 6 - 2 - 1 - 0 = 3.
    expect(isRoleAvailable("terrorist", 6, 2, [])).toBe(false);
  });

  it("allows terrorist when enough town players remain", () => {
    // 9 players, 1 mafia: mafia_alive = 1 + 1 = 2, town_alive = 9 - 1 - 1 - 0 = 7.
    expect(isRoleAvailable("terrorist", 9, 1, [])).toBe(true);
  });

  it("does not double count terrorist itself when it's already enabled", () => {
    expect(isRoleAvailable("terrorist", 9, 1, ["terrorist"])).toBe(true);
  });

  it("rejects oracle when detective is already enabled", () => {
    expect(isRoleAvailable("oracle", 6, 1, ["detective"])).toBe(false);
  });

  it("rejects detective when oracle is already enabled", () => {
    expect(isRoleAvailable("detective", 6, 1, ["oracle"])).toBe(false);
  });

  it("rejects hypnotizer when escort is already enabled", () => {
    expect(isRoleAvailable("hypnotizer", 6, 1, ["escort"])).toBe(false);
  });

  it("rejects escort when hypnotizer is already enabled", () => {
    expect(isRoleAvailable("escort", 6, 1, ["hypnotizer"])).toBe(false);
  });

  it("allows oracle when detective is not enabled", () => {
    expect(isRoleAvailable("oracle", 6, 1, [])).toBe(true);
  });
});
