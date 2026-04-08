"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
import { ChevronRight, CircleDot, Sparkles, X } from "lucide-react";
import { navItems } from "@/components/layout/nav-items";

interface SidebarProps {
    isMobileOpen: boolean;
    onMobileClose: () => void;
}

export function Sidebar({ isMobileOpen, onMobileClose }: SidebarProps) {
    const pathname = usePathname();
    const { role } = useAuthStore();
    const firstNavLinkRef = useRef<HTMLAnchorElement | null>(null);

    useEffect(() => {
        if (!isMobileOpen) {
            return;
        }
        firstNavLinkRef.current?.focus();
    }, [isMobileOpen]);

    const handleSidebarKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
        if (event.key === "Escape") {
            onMobileClose();
        }
    };

    return (
        <>
            <button
                type="button"
                aria-label="关闭侧边导航"
                aria-controls="dashboard-sidebar"
                onClick={onMobileClose}
                className={cn(
                    "fixed inset-0 z-40 bg-slate-950/88 backdrop-blur-md transition-opacity duration-300 md:hidden",
                    isMobileOpen ? "opacity-100" : "pointer-events-none opacity-0"
                )}
            />
            <aside
                id="dashboard-sidebar"
                aria-labelledby="dashboard-nav-label"
                onKeyDown={handleSidebarKeyDown}
                className={cn(
                    "fixed inset-y-0 left-0 z-50 flex h-screen w-72 max-w-[86vw] flex-col border-r border-slate-700/80 bg-slate-900/96 text-slate-100 shadow-2xl transition-transform duration-300 md:relative md:h-full md:w-72 md:max-w-none md:translate-x-0 md:rounded-2xl md:border md:border-slate-700/80 md:bg-slate-900/88 md:backdrop-blur-xl",
                    isMobileOpen ? "translate-x-0" : "-translate-x-full"
                )}
            >
                <div className="border-b border-slate-700/80 px-5 py-4">
                    <div className="flex items-start justify-between gap-2">
                        <Link href="/" scroll={false} className="flex cursor-pointer items-center gap-3">
                            <div className="relative flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary-300 via-accent-teal to-accent-gold shadow-[0_16px_30px_-18px_rgba(34,211,238,0.9)]">
                                <span className="font-mono text-lg font-semibold text-slate-950">C</span>
                                <span className="absolute -right-1 -top-1 rounded-full border border-slate-600/80 bg-slate-900 p-0.5 text-cyan-300">
                                    <Sparkles className="h-3.5 w-3.5" />
                                </span>
                            </div>
                            <div>
                                <p className="display-heading text-lg font-semibold tracking-tight text-slate-100">Cherry Trace</p>
                                <p className="text-xs tracking-wide text-slate-300">供应链实时监控</p>
                            </div>
                        </Link>
                        <button
                            type="button"
                            className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-slate-300 transition-all hover:bg-slate-800/70 hover:text-slate-100 active:scale-95 md:hidden"
                            aria-label="关闭导航"
                            aria-controls="dashboard-sidebar"
                            onClick={onMobileClose}
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>
                    <div className="edge-highlight mt-4 flex items-center gap-2 rounded-lg border border-primary-300/35 bg-primary-500/22 px-3 py-2 text-xs text-primary-100">
                        <CircleDot className="h-4 w-4 text-primary-300" />
                        流式采集已接入，系统在线
                    </div>
                </div>

<div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
                    {/* 面向非技术的业务监管员：质量、批次、预警的报表大盘 */}
                    <div>
                        <h2 id="dashboard-nav-business" className="px-2 pb-2 text-[11px] font-semibold text-slate-400 tracking-widest uppercase">
                            【 业务与品质监管 】
                        </h2>
                        <nav className="grid items-start gap-1 text-sm font-medium">
                            {navItems.filter(item => item.section === "business").map((item) => {
                                const Icon = item.icon;
                                const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
                                return (
                                    <Link
                                        key={item.href}
                                        href={item.href} scroll={false}
                                        onClick={onMobileClose}
                                        className={cn(
                                            "group relative flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-200",
                                            isActive
                                                ? "edge-highlight border border-amber-300/35 bg-amber-500/22 text-amber-100 shadow-[0_14px_26px_-18px_rgba(251,191,36,0.5)]"
                                                : "border border-transparent text-slate-300 hover:translate-x-0.5 hover:border-slate-600/80 hover:bg-slate-800/70 hover:text-slate-100"
                                        )}
                                    >
                                        <Icon className={cn("h-4 w-4", isActive ? "text-amber-400" : "text-slate-400 group-hover:text-slate-200")} />
                                        <span className="truncate">{item.title}</span>
                                        {isActive && <div className="absolute right-3 h-1.5 w-1.5 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]" />}
                                    </Link>
                                );
                            })}
                        </nav>
                    </div>

                    {/* 面向IT技术与设备实施团队：底层节点、入参分析以及上链确权 */}
                    {role === "admin" && (
                        <div>
                            <h2 id="dashboard-nav-tech" className="px-2 pb-2 text-[11px] font-semibold text-slate-400 tracking-widest uppercase">
                                【 系统配置与溯源底层 】
                            </h2>
                            <nav className="grid items-start gap-1 text-sm font-medium">
                                {navItems.filter(item => item.section === "technical").map((item) => {
                                    const Icon = item.icon;
                                    const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
                                    return (
                                        <Link
                                            key={item.href}
                                            href={item.href} scroll={false}
                                            onClick={onMobileClose}
                                            className={cn(
                                                "group relative flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-200",
                                                isActive
                                                    ? "edge-highlight border border-cyan-300/35 bg-cyan-500/22 text-cyan-100 shadow-[0_14px_26px_-18px_rgba(34,211,238,0.5)]"
                                                    : "border border-transparent text-slate-300 hover:translate-x-0.5 hover:border-slate-600/80 hover:bg-slate-800/70 hover:text-slate-100"
                                            )}
                                        >
                                            <Icon className={cn("h-4 w-4", isActive ? "text-cyan-400" : "text-slate-400 group-hover:text-slate-200")} />
                                            <span className="truncate">{item.title}</span>
                                            {isActive && <div className="absolute right-3 h-1.5 w-1.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" />}
                                        </Link>
                                    );
                                })}
                            </nav>
                        </div>
                    )}
                </div>

                <div className="border-t border-slate-700/80 p-4">
                    <div className="edge-highlight rounded-xl border border-slate-700/80 bg-slate-800/70 p-4">
                        <p className="text-xs text-slate-300">系统健康度</p>
                        <div className="mt-2 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <div className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.85)]" />
                                <span className="text-sm font-medium text-emerald-200">正常</span>
                            </div>
                            <span className="font-mono text-xs text-slate-300">24/7</span>
                        </div>
                    </div>
                </div>
            </aside>
        </>
    );
}
