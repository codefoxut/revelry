export const AVATARS = [
  { key: "fox", emoji: "🦊" },
  { key: "owl", emoji: "🦉" },
  { key: "cat", emoji: "🐱" },
  { key: "dog", emoji: "🐶" },
  { key: "bear", emoji: "🐻" },
  { key: "rabbit", emoji: "🐰" },
  { key: "wolf", emoji: "🐺" },
  { key: "deer", emoji: "🦌" },
  { key: "tiger", emoji: "🐯" },
  { key: "lion", emoji: "🦁" },
  { key: "monkey", emoji: "🐵" },
  { key: "panda", emoji: "🐼" },
  { key: "koala", emoji: "🐨" },
  { key: "frog", emoji: "🐸" },
  { key: "penguin", emoji: "🐧" },
  { key: "duck", emoji: "🦆" },
  { key: "chicken", emoji: "🐔" },
  { key: "mouse", emoji: "🐭" },
  { key: "pig", emoji: "🐷" },
  { key: "cow", emoji: "🐮" },
] as const;

const DEFAULT_EMOJI = "🙂";

export function avatarEmoji(key: string): string {
  return AVATARS.find((avatar) => avatar.key === key)?.emoji ?? DEFAULT_EMOJI;
}
