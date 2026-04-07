"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const [mobileNavOpen, setMobileNavOpen] = useState(false);
    const pathname = usePathname();
    const mainRef = useRef<HTMLElement>(null);

    // Ensure scroll resets to top of the inner container on route change,
    // avoiding the common "App shell layout scroll preservation" bug.
    useEffect(() => {
        if (mainRef.current) {
            mainRef.current.scrollTo(0, 0);
        }
    }, [pathname]);

    return (
        <div className="fixed inset-0 w-full overflow-hidden bg-[rgb(var(--background))]">
            <div aria-hidden className="pointer-events-none absolute inset-0 accent-grid opacity-55" />
            <div aria-hidden className="pointer-events-none absolute inset-0">
                <div className="absolute -left-40 top-0 h-[30rem] w-[30rem] rounded-full bg-primary-500/22 blur-[128px] animate-[aurora-shift_12s_ease-in-out_infinite]" />
                <div className="absolute right-[-100px] top-[-50px] h-[30rem] w-[30rem] rounded-full bg-cyan-400/20 blur-[136px] animate-[aurora-shift_15s_ease-in-out_infinite_reverse]" />
                <div className="absolute bottom-[-180px] left-1/3 h-[28rem] w-[28rem] rounded-full bg-amber-400/14 blur-[144px] animate-[aurora-shift_19s_ease-in-out_infinite]" />
            </div>
            <div className="relative flex h-screen w-full gap-3 p-3 md:gap-4 md:p-4 perspective-[1000px]">
                <Sidebar isMobileOpen={mobileNavOpen} onMobileClose={() => setMobileNavOpen(false)} />
                <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
                    <Header mobileNavOpen={mobileNavOpen} onOpenMobileNav={() => setMobileNavOpen(true)} />
                    <main
                        ref={mainRef}
                        id="main-content"
                        tabIndex={-1}
                        className="panel-shell edge-highlight no-scrollbar mt-3 flex-1 overflow-y-auto p-4 md:mt-4 md:p-6 transition-all duration-500 hover:shadow-[0_20px_60px_-20px_rgba(34,211,238,0.1)] hover:border-slate-600/70"
                    >
                        {children}
                    </main>
                </div>
            </div>
        </div>
    );
}
