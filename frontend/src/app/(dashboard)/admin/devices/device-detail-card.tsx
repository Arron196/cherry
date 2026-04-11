"use client";

import { Eye, Loader2 } from "lucide-react";
import { ManagedDeviceAudit, ManagedDeviceDetail, ManagedDeviceKey } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
    formatDateTime,
    formatOnlineWindowLabel,
    getDeviceStatusMeta,
    getOnlineStatusMeta,
    summarizeAuditMetadata,
    toCnAuditAction,
    toCnKeyStatus,
} from "./device-admin.utils";
import { KeyQueryState } from "./device-admin.types";

type DeviceDetailCardProps = {
    highlightSectionId: string | null;
    detailError: string;
    selectedDeviceId: string;
    selectedDeviceDetail: ManagedDeviceDetail | null;
    isDetailLoading: boolean;
    onlineWindowSeconds: number;
    detailKeyList: ManagedDeviceKey[];
    detailKeyDeviceId: string;
    detailKeyQueryState: KeyQueryState;
    detailKeyQueryMessage: string;
    detailAuditList: ManagedDeviceAudit[];
    detailAuditDeviceId: string;
    detailAuditQueryState: KeyQueryState;
    detailAuditQueryMessage: string;
    onFillRotateFromDetail: () => void;
    onFillDisableFromDetail: () => void;
    onRefreshKeyTimeline: (deviceId: string) => void;
    onRefreshAuditTimeline: (deviceId: string) => void;
};

export function DeviceDetailCard({
    highlightSectionId,
    detailError,
    selectedDeviceId,
    selectedDeviceDetail,
    isDetailLoading,
    onlineWindowSeconds,
    detailKeyList,
    detailKeyDeviceId,
    detailKeyQueryState,
    detailKeyQueryMessage,
    detailAuditList,
    detailAuditDeviceId,
    detailAuditQueryState,
    detailAuditQueryMessage,
    onFillRotateFromDetail,
    onFillDisableFromDetail,
    onRefreshKeyTimeline,
    onRefreshAuditTimeline,
}: DeviceDetailCardProps) {
    const selectedDeviceStatusMeta = selectedDeviceDetail ? getDeviceStatusMeta(selectedDeviceDetail.status) : null;
    const selectedDeviceOnlineStatusMeta = selectedDeviceDetail
        ? getOnlineStatusMeta(selectedDeviceDetail.last_seen_at, onlineWindowSeconds)
        : null;

    return (
        <Card
            id="section-device-detail"
            className={cn(
                "panel-shell edge-highlight border-slate-700/75 transition-[border-color,box-shadow] duration-300",
                highlightSectionId === "section-device-detail" && "border-primary-400/60 shadow-[0_0_0_1px_rgba(74,222,128,0.4),0_0_34px_-12px_rgba(34,197,94,0.85)]"
            )}
        >
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Eye className="h-5 w-5 text-cyan-400" />
                    设备详情
                </CardTitle>
            </CardHeader>
            <CardContent>
                {detailError ? (
                    <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                        {detailError}
                    </div>
                ) : null}

                {!selectedDeviceId && !isDetailLoading && !selectedDeviceDetail ? (
                    <p className="text-sm text-slate-300">请在设备列表点击“查看详情”查看单设备信息。</p>
                ) : null}

                {isDetailLoading && (
                    <div className="flex items-center text-sm text-slate-300">
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 正在加载设备详情...
                    </div>
                )}

                {selectedDeviceDetail ? (
                    <div className="space-y-4 text-sm">
                        <div className="grid gap-4 lg:grid-cols-2">
                            <div className="group edge-highlight rounded-xl border border-slate-700/75 bg-slate-900/55 p-4 transition-all duration-300 hover:border-cyan-400/40 hover:bg-slate-800/80 hover:shadow-[0_12px_24px_-10px_rgba(34,211,238,0.15)] hover:-translate-y-0.5">
                                <p className="text-xs uppercase tracking-[0.14em] text-slate-300 group-hover:text-cyan-300 transition-colors">基础信息</p>
                                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                                    <div>
                                        <p className="text-slate-300">设备 ID</p>
                                        <p className="font-mono text-slate-100 group-hover:text-white transition-colors">{selectedDeviceDetail.device_id}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-300">设备名称</p>
                                        <p className="text-slate-100 group-hover:text-white transition-colors">{selectedDeviceDetail.name || "未命名设备"}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-300">注册时间</p>
                                        <p className="text-slate-100 group-hover:text-white transition-colors">{formatDateTime(selectedDeviceDetail.created_at)}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-300">最近在线时间</p>
                                        <p className="text-slate-100 group-hover:text-white transition-colors">{formatDateTime(selectedDeviceDetail.last_seen_at)}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-300">密钥总数</p>
                                        <p className="text-slate-100 group-hover:text-white transition-colors">{selectedDeviceDetail.key_count}</p>
                                    </div>
                                </div>
                            </div>

                            <div className="group edge-highlight rounded-xl border border-slate-700/75 bg-slate-900/55 p-4 transition-all duration-300 hover:border-emerald-400/40 hover:bg-slate-800/80 hover:shadow-[0_12px_24px_-10px_rgba(16,185,129,0.15)] hover:-translate-y-0.5">
                                <p className="text-xs uppercase tracking-[0.14em] text-slate-300 group-hover:text-emerald-300 transition-colors">运行状态</p>
                                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                                    <div>
                                        <p className="text-slate-300">启用状态</p>
                                        <Badge variant={selectedDeviceStatusMeta!.variant}>{selectedDeviceStatusMeta!.label}</Badge>
                                    </div>
                                    <div>
                                        <p className="text-slate-300">在线状态</p>
                                        <Badge variant={selectedDeviceOnlineStatusMeta!.variant}>{selectedDeviceOnlineStatusMeta!.label}</Badge>
                                        <p className="mt-1 text-xs text-slate-300">阈值：{formatOnlineWindowLabel(onlineWindowSeconds)}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-300">近 24 小时签名失败</p>
                                        <p className="text-slate-100">{selectedDeviceDetail.signature_failures_last_24h ?? 0}</p>
                                    </div>
                                </div>
                                <div className="mt-3 rounded-md border border-slate-700/75 bg-slate-950/45 px-3 py-2">
                                    <p className="text-slate-300">离线/在线解释（后端判定）</p>
                                    <p className="mt-1 break-words text-slate-100">{selectedDeviceDetail.online_status_explanation || "暂无"}</p>
                                </div>
                                <div className="mt-2 rounded-md border border-slate-700/75 bg-slate-950/45 px-3 py-2">
                                    <p className="text-slate-300">最近签名失败原因</p>
                                    <p className="mt-1 break-all font-mono text-slate-100">{selectedDeviceDetail.latest_signature_failure_reason || "无"}</p>
                                </div>
                            </div>
                        </div>

                        <div className="grid gap-4 lg:grid-cols-2">
                            <div className="group edge-highlight rounded-xl border border-slate-700/75 bg-slate-900/55 p-4 transition-all duration-300 hover:border-amber-400/40 hover:bg-slate-800/80 hover:shadow-[0_12px_24px_-10px_rgba(251,191,36,0.15)] hover:-translate-y-0.5">
                                <p className="mb-2 text-slate-300 group-hover:text-amber-300 transition-colors uppercase tracking-[0.14em] text-xs">当前生效密钥</p>
                                {selectedDeviceDetail.active_key ? (
                                    <div className="space-y-1 text-slate-200">
                                        <p className="font-mono group-hover:text-white transition-colors">Key ID：{selectedDeviceDetail.active_key.key_id}</p>
                                        <p className="group-hover:text-white transition-colors">算法：{selectedDeviceDetail.active_key.algorithm}</p>
                                        <p className="group-hover:text-white transition-colors">状态：{toCnKeyStatus(selectedDeviceDetail.active_key.status)}</p>
                                        <p className="group-hover:text-white transition-colors">生效时间：{formatDateTime(selectedDeviceDetail.active_key.activated_at)}</p>
                                    </div>
                                ) : (
                                    <p className="text-slate-300">当前暂无生效密钥。</p>
                                )}
                            </div>

                            <div className="group edge-highlight rounded-xl border border-slate-700/75 bg-slate-900/55 p-4 transition-all duration-300 hover:border-primary-400/40 hover:bg-slate-800/80 hover:shadow-[0_12px_24px_-10px_rgba(16,185,129,0.15)] hover:-translate-y-0.5">
                                <p className="mb-3 text-slate-300 group-hover:text-primary-300 transition-colors uppercase tracking-[0.14em] text-xs">快捷操作</p>
                                <div className="flex flex-wrap gap-2">
                                    <Button type="button" size="sm" variant="outline" className="cursor-pointer" onClick={onFillRotateFromDetail}>
                                        填充到密钥轮换
                                    </Button>
                                    <Button type="button" size="sm" variant="outline" className="cursor-pointer" onClick={onFillDisableFromDetail}>
                                        填充到停用设备
                                    </Button>
                                    <Button
                                        type="button"
                                        size="sm"
                                        variant="secondary"
                                        className="cursor-pointer"
                                        disabled={!selectedDeviceDetail.device_id || detailKeyQueryState === "loading"}
                                        onClick={() => onRefreshKeyTimeline(selectedDeviceDetail.device_id)}
                                    >
                                        {detailKeyQueryState === "loading" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                                        刷新密钥时间线
                                    </Button>
                                    <Button
                                        type="button"
                                        size="sm"
                                        variant="secondary"
                                        className="cursor-pointer"
                                        disabled={!selectedDeviceDetail.device_id || detailAuditQueryState === "loading"}
                                        onClick={() => onRefreshAuditTimeline(selectedDeviceDetail.device_id)}
                                    >
                                        {detailAuditQueryState === "loading" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                                        刷新审计时间线
                                    </Button>
                                </div>
                            </div>
                        </div>

                        <div className="grid gap-4 lg:grid-cols-2">
                            <div className="edge-highlight rounded-xl border border-slate-700/75 bg-slate-900/55 p-4">
                                <p className="mb-2 text-slate-300">密钥历史时间线</p>
                                <p className="mb-3 text-xs text-slate-300">设备：{detailKeyDeviceId || selectedDeviceDetail.device_id}</p>
                                {detailKeyQueryMessage ? <p className="mb-2 text-sm text-slate-300">{detailKeyQueryMessage}</p> : null}

                                {detailKeyQueryState === "loading" && (
                                    <div className="flex items-center text-sm text-slate-300">
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 正在加载密钥时间线...
                                    </div>
                                )}

                                {detailKeyQueryState === "loaded" && detailKeyList.length === 0 && (
                                    <p className="text-sm text-slate-300">当前没有密钥历史记录。</p>
                                )}

                                {detailKeyQueryState === "loaded" && detailKeyList.length > 0 && (
                                    <div className="space-y-3 border-l border-white/15 pl-3">
                                        {detailKeyList.map((item) => (
                                            <div key={item.key_id} className="rounded border border-slate-700/75 bg-slate-950/45 px-3 py-2 text-sm text-slate-200">
                                                <p className="font-mono text-slate-100">Key ID：{item.key_id}</p>
                                                <p>算法：{item.algorithm}</p>
                                                <p>状态：{toCnKeyStatus(item.status)}</p>
                                                <p>生效时间：{formatDateTime(item.activated_at)}</p>
                                                <p>退役时间：{formatDateTime(item.retired_at)}</p>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="edge-highlight rounded-xl border border-slate-700/75 bg-slate-900/55 p-4">
                                <p className="mb-2 text-slate-300">设备操作审计时间线</p>
                                <p className="mb-3 text-xs text-slate-300">设备：{detailAuditDeviceId || selectedDeviceDetail.device_id}</p>
                                {detailAuditQueryMessage ? <p className="mb-2 text-sm text-slate-300">{detailAuditQueryMessage}</p> : null}

                                {detailAuditQueryState === "loading" && (
                                    <div className="flex items-center text-sm text-slate-300">
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 正在加载审计时间线...
                                    </div>
                                )}

                                {detailAuditQueryState === "loaded" && detailAuditList.length === 0 && (
                                    <p className="text-sm text-slate-300">当前没有审计记录。</p>
                                )}

                                {detailAuditQueryState === "loaded" && detailAuditList.length > 0 && (
                                    <div className="space-y-3 border-l border-white/15 pl-3">
                                        {detailAuditList.map((item) => {
                                            const summaryLines = summarizeAuditMetadata(item);
                                            return (
                                                <div key={String(item.audit_id)} className="rounded border border-slate-700/75 bg-slate-950/45 px-3 py-2 text-sm text-slate-200">
                                                    <p>审计 ID：{item.audit_id}</p>
                                                    <p>操作：{toCnAuditAction(item.action)}</p>
                                                    <p>操作者：{item.actor}</p>
                                                    <p>目标：{item.target}</p>
                                                    <p>时间：{formatDateTime(item.created_at)}</p>
                                                    {summaryLines.map((line) => (
                                                        <p key={`${item.audit_id}-${line}`} className="text-slate-300">
                                                            {line}
                                                        </p>
                                                    ))}
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                ) : null}
            </CardContent>
        </Card>
    );
}
