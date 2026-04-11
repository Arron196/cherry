"use client";

import { ReactNode } from "react";
import { FeedbackState } from "./device-admin.types";
import { scrollToSection } from "./device-admin.utils";

type DeviceAdminPageChromeProps = {
    feedback: FeedbackState;
};

export function DeviceAdminPageChrome({ feedback }: DeviceAdminPageChromeProps) {
    return (
        <>
            <section className="panel-shell edge-highlight p-5 md:p-6">
                <h1 className="display-heading mb-2 text-2xl font-semibold tracking-tight text-white md:text-3xl">设备管理</h1>
                <p className="text-sm text-slate-300">覆盖设备注册、密钥轮换、停用与审计信息回溯。</p>
            </section>

            {feedback && (
                <div
                    className={`edge-highlight rounded-md border px-3 py-2 text-sm ${feedback.type === "ok"
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                        : "border-red-500/30 bg-red-500/10 text-red-300"
                        }`}
                >
                    {feedback.text}
                </div>
            )}

            <div className="edge-highlight flex flex-wrap gap-2 rounded-md border border-slate-700/75 bg-slate-900/55 p-2">
                <button type="button" onClick={(e) => { e.preventDefault(); scrollToSection("section-device-overview"); }} className="cursor-pointer inline-flex items-center justify-center rounded-md border border-slate-700/75 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 transition-all hover:border-cyan-400/40 hover:bg-slate-800/70 hover:-translate-y-px">设备总览</button>
                <button type="button" onClick={(e) => { e.preventDefault(); scrollToSection("section-device-detail"); }} className="cursor-pointer inline-flex items-center justify-center rounded-md border border-slate-700/75 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 transition-all hover:border-cyan-400/40 hover:bg-slate-800/70 hover:-translate-y-px">设备详情</button>
                <button type="button" onClick={(e) => { e.preventDefault(); scrollToSection("section-device-high-frequency"); }} className="cursor-pointer inline-flex items-center justify-center rounded-md border border-slate-700/75 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 transition-all hover:border-cyan-400/40 hover:bg-slate-800/70 hover:-translate-y-px">高频操作</button>
                <button type="button" onClick={(e) => { e.preventDefault(); scrollToSection("section-device-low-frequency"); }} className="cursor-pointer inline-flex items-center justify-center rounded-md border border-slate-700/75 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 transition-all hover:border-cyan-400/40 hover:bg-slate-800/70 hover:-translate-y-px">低频工具</button>
            </div>
        </>
    );
}

export function DeviceHighFrequencyIntro() {
    return (
        <div className="edge-highlight order-0 rounded-md border border-slate-700/75 bg-slate-900/55 px-4 py-3 text-sm text-slate-300 md:col-span-2">
            <p className="font-medium text-slate-100">高频操作</p>
            <p className="mt-1 text-xs text-slate-300">按日常管理优先排序：注册新设备、密钥轮换、停用设备。</p>
            <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" onClick={(e) => { e.preventDefault(); scrollToSection("section-device-register"); }} className="cursor-pointer rounded border border-slate-700/75 bg-slate-900 px-2.5 py-1 text-xs text-slate-200 transition-all hover:border-cyan-400/40 hover:bg-slate-800/70 hover:-translate-y-px">注册</button>
                <button type="button" onClick={(e) => { e.preventDefault(); scrollToSection("section-device-rotate"); }} className="cursor-pointer rounded border border-slate-700/75 bg-slate-900 px-2.5 py-1 text-xs text-slate-200 transition-all hover:border-cyan-400/40 hover:bg-slate-800/70 hover:-translate-y-px">轮换</button>
                <button type="button" onClick={(e) => { e.preventDefault(); scrollToSection("section-device-disable"); }} className="cursor-pointer rounded border border-slate-700/75 bg-slate-900 px-2.5 py-1 text-xs text-slate-200 transition-all hover:border-cyan-400/40 hover:bg-slate-800/70 hover:-translate-y-px">停用</button>
            </div>
        </div>
    );
}

type DeviceLowFrequencyShellProps = {
    children: ReactNode;
};

export function DeviceLowFrequencyShell({ children }: DeviceLowFrequencyShellProps) {
    return (
        <details id="section-device-low-frequency" className="edge-highlight order-4 rounded-md border border-slate-700/75 bg-slate-900/55 md:col-span-2">
            <summary className="cursor-pointer list-none px-4 py-3 text-sm text-slate-300">
                <p className="font-medium text-slate-100">低频工具（默认折叠）</p>
                <p className="mt-1 text-xs text-slate-300">接入向导与测试事件用于联调/排障，点击展开后显示完整内容。</p>
            </summary>

            <div className="grid gap-6 border-t border-slate-700/75 p-4 md:grid-cols-2">{children}</div>
        </details>
    );
}
