import { SiteNav } from "@/components/SiteNav";

export default function SiteLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <SiteNav />
      {children}
    </>
  );
}
