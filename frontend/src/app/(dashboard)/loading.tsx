import { Loader2 } from "lucide-react";

export default function DashboardLoading() {
    return (
        <div className="space-y-7">
            <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 animate-spin text-primary-500" />
                <p className="text-sm text-slate-300">正在加载仪表盘数据，请稍候...</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {Array.from({ length: 4 }).map((_, index) => (
                    <div key={index} className="panel-shell edge-highlight h-28 animate-pulse border-slate-700/50 bg-slate-900/60" />
                ))}
            </div>

            <div className="grid gap-4 lg:grid-cols-7">
                <div className="panel-shell edge-highlight h-72 animate-pulse lg:col-span-4" />
                <div className="panel-shell edge-highlight h-72 animate-pulse lg:col-span-3" />
            </div>
        </div>
    );
}
