import { Link, useRouterState } from "@tanstack/react-router";
import { Search, ClipboardCheck, Sparkles, Activity, Github } from "lucide-react";
import type { ReactNode } from "react";

const nav = [
  { to: "/", label: "Search Engine", icon: Search, badge: "Core" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="hidden md:flex fixed inset-y-0 left-0 w-64 flex-col border-r border-border/70 bg-[color-mix(in_oklab,var(--ivory)_92%,white)] backdrop-blur-xl z-20">
        <div className="px-6 pt-7 pb-6 flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl gradient-primary flex items-center justify-center periwinkle-glow">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="text-[15px] font-semibold tracking-tight">InfoByte</div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
              Routing Intelligence
            </div>
          </div>
        </div>

        <nav className="px-3 mt-2 flex flex-col gap-1">
          {nav.map((item) => {
            const active = pathname === item.to;
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all ${
                  active
                    ? "bg-white periwinkle-glow text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-white/60"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span className="flex-1 font-medium">{item.label}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-md border ${
                    active
                      ? "border-primary/40 text-primary bg-primary/5"
                      : "border-border text-muted-foreground"
                  }`}
                >
                  {item.badge}
                </span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto p-4">
          <div className="glass-card rounded-2xl p-4">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
              <Activity className="h-3.5 w-3.5" />
              System status
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-lg font-semibold tracking-tight">Operational</span>
              <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_10px_2px_rgba(16,185,129,0.6)]" />
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              7 sources · 99.98% uptime
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between px-2 text-[11px] text-muted-foreground">
            <span>v2.4.1</span>
            <a className="inline-flex items-center gap-1 hover:text-foreground" href="#">
              <Github className="h-3.5 w-3.5" /> docs
            </a>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 md:pl-64 min-h-screen">
        <div className="mx-auto w-full max-w-[1300px] px-6 md:px-10 py-8 md:py-12">
          {children}
        </div>
      </main>
    </div>
  );
}
