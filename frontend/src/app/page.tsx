"use client";

import { useEffect, useState } from "react";
import { LandingPage } from "@/components/landing/LandingPage";
import { DashboardShell } from "@/components/dashboard/DashboardShell";

type View = "landing" | "dashboard";

/**
 * AFTERMATH — single-route experience.
 * The landing page and the application dashboard share one route and one
 * visual world: a paper card floating on deep forest green.
 */
export default function Home() {
  const [view, setView] = useState<View>("landing");

  // Preserve the landing scroll position when returning from the dashboard.
  const [landingScroll, setLandingScroll] = useState(0);

  const openDashboard = () => {
    setLandingScroll(window.scrollY);
    setView("dashboard");
  };

  const exitDashboard = () => setView("landing");

  useEffect(() => {
    if (view === "dashboard") {
      window.scrollTo({ top: 0, behavior: "auto" });
    } else {
      window.scrollTo({ top: landingScroll, behavior: "auto" });
    }
  }, [view, landingScroll]);

  return (
    <div className="flex min-h-screen flex-col bg-forest-deep">
      <div className="texture-paper relative mx-2 flex min-h-[calc(100vh-1rem)] flex-col overflow-x-guard rounded-[1.25rem] border-2 border-ink bg-paper shadow-[0_6px_0_rgba(4,54,28,0.6)] sm:mx-3 sm:min-h-[calc(100vh-1.5rem)] sm:rounded-[1.75rem] md:mx-4 lg:mx-6 lg:min-h-[calc(100vh-3rem)] lg:rounded-[2.5rem]">
        {view === "landing" ? (
          <LandingPage onOpenDashboard={openDashboard} />
        ) : (
          <DashboardShell onExit={exitDashboard} />
        )}
      </div>
    </div>
  );
}
