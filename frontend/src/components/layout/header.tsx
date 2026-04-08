"use client";

import { useMemo, useState } from "react";
import { useAuthStore } from "@/hooks/use-auth";
import { useSimulationStore } from "@/hooks/use-simulation";
import { Button } from "@/components/ui/button";
import { CalendarDays, Loader2, LogOut, Menu, ShieldCheck, User, Radio, Server } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { navItems } from "@/components/layout/nav-items";

interface HeaderProps {
    mobileNavOpen: boolean;
    onOpenMobileNav: () => void;
}

export function Header({ mobileNavOpen, onOpenMobileNav }: HeaderProps) {
    const { role, logout } = useAuthStore();
    const pathname = usePathname();
    const router = useRouter();
    const { isSimulating, setSimulation } = useSimulationStore();
    const [isSwitchingSimulation, setIsSwitchingSimulation] = useState(false);

    const roleText = role === "admin" ? "管理员" : role === "regulator" ? "监管员" : "访客";
    const activeNav = navItems.find((item) => pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href)));
    const todayLabel = useMemo(
        () =>
            new Intl.DateTimeFormat("zh-CN", {
                year: "numeric",
                month: "short",
                day: "numeric",
                weekday: "short",
            }).format(new Date()),
        []
    );

    const handleLogout = () => {
        logout();
        router.push("/login");
    };

    const handleSimulationToggle = async () => {
        if (isSwitchingSimulation) {
            return;
        }

        const nextValue = !isSimulating;
        setIsSwitchingSimulation(true);
        try {
            setSimulation(nextValue);
        } catch (error) {
            console.error("Failed to switch simulation generator", error);
        } finally {
            setIsSwitchingSimulation(false);
        }
    };

    return (
        <header className="edge-highlight sticky top-0 z-30 flex min-h-16 w-full items-center gap-3 rounded-2xl border border-slate-700/75 bg-slate-900/86 px-4 py-3 shadow-[0_24px_50px_-34px_rgba(2,6,23,0.9)] backdrop-blur-xl md:px-5">
            <Button
                type="button"
                size="icon"
                variant="ghost"
                className="md:hidden"
                onClick={onOpenMobileNav}
                aria-label="打开导航"
                aria-expanded={mobileNavOpen}
                aria-controls="dashboard-sidebar"
            >
                <Menu className="h-5 w-5" />
            </Button>

            <div className="min-w-0 flex-1">
                <p className="display-heading truncate text-lg font-semibold tracking-tight text-slate-100">
                    {activeNav ? activeNav.title : "控制台"}
                </p>
                <div className="mt-1 hidden items-center gap-2 text-xs text-slate-300 sm:flex">
                    <CalendarDays className="h-4 w-4" />
                    <span>{todayLabel}</span>
                    <span className="h-1 w-1 rounded-full bg-slate-500" />
                    <span>实时数据面板</span>
                </div>
            </div>

            <div className="edge-highlight hidden items-center gap-2 rounded-lg border border-primary-300/35 bg-primary-500/22 px-2.5 py-1.5 text-xs text-primary-100 sm:flex">
                <ShieldCheck className="h-4 w-4" />
                数据链路正常
            </div>

            {role === "admin" && (
                <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={handleSimulationToggle}
                    disabled={isSwitchingSimulation}
                    className={`hidden sm:flex transition-all duration-300 ${isSimulating ? 'text-primary-300 border-primary-500/50 bg-primary-500/10' : 'text-slate-400 border-slate-700 hover:text-slate-200 hover:bg-slate-800'}`}
                >
                    {isSwitchingSimulation ? (
                        <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    ) : isSimulating ? (
                        <Radio className="mr-1.5 h-4 w-4 animate-pulse" />
                    ) : (
                        <Server className="mr-1.5 h-4 w-4 text-cyan-400" />
                    )}
                    {isSimulating ? '脱机仿真(流式)' : '真实网关(侦听中)'}
                </Button>
            )}

            {role ? (
                <div className="flex items-center gap-2">
                    <div className="edge-highlight hidden items-center gap-2 rounded-lg border border-slate-700/75 bg-slate-800/75 px-2.5 py-1.5 text-xs text-slate-100 sm:flex">
                        <User className="h-4 w-4 text-slate-200" />
                        <span>{roleText}</span>
                    </div>
                    <Button variant="outline" size="sm" onClick={handleLogout}>
                        <LogOut className="mr-1.5 h-4 w-4" />
                        退出
                    </Button>
                </div>
            ) : (
                <Button variant="default" size="sm" onClick={() => router.push("/login")}>
                    去登录
                </Button>
            )}
        </header>
    );
}
