"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface DashboardErrorProps {
    error: Error & { digest?: string };
    reset: () => void;
}

export default function DashboardError({ error, reset }: DashboardErrorProps) {
    useEffect(() => {
        console.error(error);
    }, [error]);

    return (
        <div className="flex min-h-[60vh] items-center justify-center px-4">
            <div className="panel-shell edge-highlight w-full max-w-lg border-status-error/30 p-6 text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-status-error/30 bg-status-error/10">
                    <AlertTriangle className="h-6 w-6 text-status-error" />
                </div>
                <h2 className="display-heading text-xl font-semibold text-white md:text-2xl">页面加载失败</h2>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                    仪表盘遇到临时异常，可能是网络波动或服务短暂不可用。请点击下方按钮重试。
                </p>
                {error.message ? (
                    <p className="edge-highlight mt-4 rounded-md border border-slate-700 bg-slate-900/60 px-3 py-2 text-left text-xs text-slate-300">
                        错误信息：{error.message}
                    </p>
                ) : null}
                <div className="mt-6 flex justify-center">
                    <Button type="button" onClick={reset}>
                        重试加载
                    </Button>
                </div>
            </div>
        </div>
    );
}
