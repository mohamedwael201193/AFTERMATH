"use client";

import { useEffect, useState } from "react";
import { Menu, ArrowRight, LayoutDashboard } from "lucide-react";
import { AftermathWordmark } from "@/components/artwork/AftermathMark";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { href: "#product", label: "Product" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#trust", label: "Trust & safety" },
];

/**
 * Floating pill navigation — rounded forest-green capsule that sits over
 * the paper card, with a white active pill and a dashboard CTA.
 */
export function LandingNav({ onOpenDashboard }: { onOpenDashboard: () => void }) {
  const [active, setActive] = useState<string>("");

  useEffect(() => {
    const ids = NAV_LINKS.map((l) => l.href.slice(1));
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) setActive(`#${e.target.id}`);
        }
      },
      { rootMargin: "-40% 0px -55% 0px" }
    );
    for (const id of ids) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);

  return (
    <header className="sticky top-0 z-40 px-3 pt-3 sm:px-5 sm:pt-4">
      <nav
        aria-label="Primary"
        className="mx-auto flex max-w-4xl items-center gap-1 rounded-full border-2 border-ink bg-forest-deep px-2 py-1.5 shadow-[0_6px_0_rgba(4,54,28,0.45)] sm:gap-2 sm:px-3"
      >
        <a
          href="#top"
          className="on-forest rounded-full px-2 py-1 focus-visible:outline-paper"
          aria-label="AFTERMATH home"
        >
          <AftermathWordmark on="forest" withBadge={false} className="[&_span]:text-paper" />
        </a>

        <div className="ml-2 hidden items-center gap-0.5 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={cn(
                "rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
                active === link.href
                  ? "bg-paper text-forest-deep"
                  : "text-paper/85 hover:bg-paper/15 hover:text-paper"
              )}
            >
              {link.label}
            </a>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Button
            onClick={onOpenDashboard}
            size="sm"
            className="group hidden gap-1.5 rounded-full bg-paper px-4 font-semibold text-forest-deep shadow-[0_3px_0_rgba(23,25,22,0.9)] transition-transform hover:-translate-y-0.5 hover:shadow-[0_5px_0_rgba(23,25,22,0.9)] active:translate-y-0 active:shadow-[0_2px_0_rgba(23,25,22,0.9)] sm:inline-flex"
          >
            <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
            Open dashboard
            <ArrowRight
              className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </Button>

          {/* Mobile menu */}
          <Sheet>
            <SheetTrigger asChild>
              <button
                aria-label="Open menu"
                className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-paper/12 text-paper transition-colors hover:bg-paper/20 md:hidden"
              >
                <Menu className="h-5 w-5" aria-hidden="true" />
              </button>
            </SheetTrigger>
            <SheetContent
              side="top"
              aria-describedby={undefined}
              className="rounded-b-3xl border-2 border-ink bg-forest-deep text-paper [&>button]:text-paper"
            >
              <SheetHeader className="text-left">
                <SheetTitle className="flex items-center text-paper">
                  <AftermathWordmark on="forest" withBadge={false} />
                </SheetTitle>
              </SheetHeader>
              <div className="grid gap-2 px-4 pb-6">
                {NAV_LINKS.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    className="rounded-2xl border border-paper/25 px-4 py-3 text-base font-medium text-paper hover:bg-paper/10"
                  >
                    {link.label}
                  </a>
                ))}
                <Button
                  onClick={onOpenDashboard}
                  className="mt-2 gap-1.5 rounded-2xl bg-paper font-semibold text-forest-deep"
                >
                  <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
                  Open dashboard
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </nav>
    </header>
  );
}
