import Link from "next/link";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/roles", label: "Roles" },
  { href: "/gameplay", label: "Gameplay" },
  { href: "/tie-breakers", label: "Tie-Breakers" },
  { href: "/rules", label: "Rules" },
  { href: "/faq", label: "FAQ" },
];

export function SiteNav() {
  return (
    <nav className="flex w-full justify-center border-b border-zinc-800 bg-zinc-950 px-6 py-4">
      <ul className="flex w-full max-w-3xl flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm font-medium text-zinc-400">
        {LINKS.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className="transition-colors hover:text-rose-400">
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
