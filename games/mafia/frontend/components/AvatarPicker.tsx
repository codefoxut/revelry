import { AVATARS } from "@/lib/avatars";

export function AvatarPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2" role="radiogroup" aria-label="Choose an avatar">
      {AVATARS.map((avatar) => (
        <button
          key={avatar.key}
          type="button"
          role="radio"
          aria-checked={value === avatar.key}
          onClick={() => onChange(avatar.key)}
          className={`flex h-10 w-10 items-center justify-center rounded-full border text-xl transition-colors ${
            value === avatar.key
              ? "border-rose-500 bg-rose-950/50"
              : "border-zinc-800 bg-zinc-900 hover:border-zinc-600"
          }`}
        >
          {avatar.emoji}
        </button>
      ))}
    </div>
  );
}
