"use client";

import { Eye, Loader2, Server, Copy, Check, Inbox, RefreshCcw } from "lucide-react";
import { useState } from "react";
import { ManagedDevice } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
    DeviceStatusView,
    ONLINE_WINDOW_OPTIONS,
    PAGE_SIZE_OPTIONS,
    extractErrorDetail,
    formatDateTime,
    formatRelativeTime,
    formatOnlineWindowLabel,
    getDeviceStatusMeta,
    getOnlineStatusMeta,
    truncateId,
} from "./device-admin.utils";

function CopyableId({ id }: { id: string }) {
    const [copied, setCopied] = useState(false);
    
    const handleCopy = () => {
        navigator.clipboard.writeText(id);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="flex items-center gap-1.5 group/copy">
            <span title={id}>{truncateId(id, 12)}</span>
            <button 
                onClick={handleCopy}
                className="opacity-0 group-hover/copy:opacity-100 transition-opacity p-1 hover:bg-slate-700/50 rounded-md text-slate-400 hover:text-cyan-300"
                title="复制 ID"
            >
                {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
            </button>
        </div>
    );
}

type DeviceOverviewCardProps = {
    devices: ManagedDevice[];
    isLoading: boolean;
    isFetching: boolean;
    isError: boolean;
    error: unknown;
    totalDevices: number;
    totalPages: number;
    displayCurrentPage: number;
    statusFilter: DeviceStatusView;
    pageEnabledDevices: number;
    pageDisabledDevices: number;
    pageOnlineDevices: number;
    onlineWindowSeconds: number;
    pageSize: number;
    pageJumpInput: string;
    selectedDeviceId: string;
    isDetailLoading: boolean;
    onStatusFilterChange: (value: DeviceStatusView) => void;
    onOnlineWindowSecondsChange: (value: number) => void;
    onRefresh: () => void;
    onViewDetail: (deviceId: string) => void;
    onPrepareRotate: (deviceId: string) => void;
    onPrepareDisable: (deviceId: string) => void;
    onPageSizeChange: (value: number) => void;
    onFirstPage: () => void;
    onPreviousPage: () => void;
    onNextPage: () => void;
    onLastPage: () => void;
    onPageJumpInputChange: (value: string) => void;
    onPageJump: () => void;
};

export function DeviceOverviewCard({
    devices,
    isLoading,
    isFetching,
    isError,
    error,
    totalDevices,
    totalPages,
    displayCurrentPage,
    statusFilter,
    pageEnabledDevices,
    pageDisabledDevices,
    pageOnlineDevices,
    onlineWindowSeconds,
    pageSize,
    pageJumpInput,
    selectedDeviceId,
    isDetailLoading,
    onStatusFilterChange,
    onOnlineWindowSecondsChange,
    onRefresh,
    onViewDetail,
    onPrepareRotate,
    onPrepareDisable,
    onPageSizeChange,
    onFirstPage,
    onPreviousPage,
    onNextPage,
    onLastPage,
    onPageJumpInputChange,
    onPageJump,
}: DeviceOverviewCardProps) {
    return (
        <Card id="section-device-overview" className="panel-shell edge-highlight border-slate-700/75">
            <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <CardTitle className="flex items-center gap-2">
                        <Server className="h-5 w-5 text-primary-500" />
                        设备列表
                    </CardTitle>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                        <span className="rounded-full border border-slate-700/75 bg-slate-900/45 px-2.5 py-1 text-slate-200">
                            当前页设备 {devices.length}
                        </span>
                        <span className="rounded-full border border-emerald-400/35 bg-emerald-500/15 px-2.5 py-1 text-emerald-300">
                            在线 {pageOnlineDevices}
                        </span>
                        <span className="rounded-full border border-cyan-400/35 bg-cyan-500/15 px-2.5 py-1 text-cyan-300">
                            启用 {pageEnabledDevices}
                        </span>
                        <span className="rounded-full border border-red-400/35 bg-red-500/15 px-2.5 py-1 text-red-300">
                            停用 {pageDisabledDevices}
                        </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" variant={statusFilter === "all" ? "default" : "secondary"} onClick={() => onStatusFilterChange("all")}>
                            全部
                        </Button>
                        <Button size="sm" variant={statusFilter === "active" ? "default" : "secondary"} onClick={() => onStatusFilterChange("active")}>
                            已启用
                        </Button>
                        <Button size="sm" variant={statusFilter === "disabled" ? "default" : "secondary"} onClick={() => onStatusFilterChange("disabled")}>
                            已停用
                        </Button>
                        <label className="ml-1 inline-flex items-center gap-2 rounded border border-slate-700/75 bg-slate-900/45 px-2 py-1 text-xs text-slate-300">
                            在线阈值
                            <select
                                className="rounded border border-slate-700/75 bg-slate-900 px-1 py-0.5 text-slate-200"
                                value={onlineWindowSeconds}
                                onChange={(event) => onOnlineWindowSecondsChange(Number(event.target.value))}
                            >
                                {ONLINE_WINDOW_OPTIONS.map((option) => (
                                    <option key={option} value={option}>
                                        {formatOnlineWindowLabel(option)}
                                    </option>
                                ))}
                            </select>
                        </label>
                    </div>
                </div>
                <Button variant="outline" size="sm" onClick={onRefresh} disabled={isFetching}>
                    {isFetching ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCcw className="mr-2 h-4 w-4" />}
                    刷新列表
                </Button>
            </CardHeader>
            <CardContent>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>device_id</TableHead>
                            <TableHead>name</TableHead>
                            <TableHead>状态</TableHead>
                            <TableHead>在线状态</TableHead>
                            <TableHead>last_seen_at</TableHead>
                            <TableHead>created_at</TableHead>
                            <TableHead>操作</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {isLoading && (
                            <TableRow>
                                <TableCell colSpan={7} className="text-center text-slate-300">
                                    正在加载设备列表，请稍候...
                                </TableCell>
                            </TableRow>
                        )}

                        {isError && (
                            <TableRow>
                                <TableCell colSpan={7} className="text-center text-red-300">
                                    设备列表加载失败：{extractErrorDetail(error, "请稍后重试")}
                                </TableCell>
                            </TableRow>
                        )}

                        {!isLoading && !isError && devices.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={7} className="h-64 text-center">
                                    <div className="flex flex-col items-center justify-center gap-3 text-slate-400">
                                        <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-800/50 shadow-inner">
                                            <Inbox className="h-8 w-8 text-slate-500" />
                                            <div className="absolute -bottom-1 -right-1 h-3 w-3 rounded-full bg-cyan-400/20 blur-sm" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-slate-300">当前暂无设备</p>
                                            <p className="mt-1 text-xs">请在下方表单中点击「注册新设备」开始接入</p>
                                        </div>
                                    </div>
                                </TableCell>
                            </TableRow>
                        )}

                        {!isLoading && !isError && devices.map((device, idx) => {
                            const statusMeta = getDeviceStatusMeta(device.status);
                            const onlineStatusMeta = getOnlineStatusMeta(device.last_seen_at, onlineWindowSeconds);
                            // Use basic delay for staggered entrance without framer-motion on table tr
                            const delayStyle = { animationDelay: `${idx * 50}ms`, animationFillMode: "both" };
                            return (
                                <TableRow 
                                    key={`${device.device_id}-${device.created_at}`} 
                                    className="group hover:bg-slate-800/85 hover:shadow-[inset_0_0_12px_rgba(34,211,238,0.15)] transition-all duration-300 animate-[slide-up-fade_0.4s_ease-out_forwards]" 
                                    style={delayStyle}
                                >
                                    <TableCell className="font-mono text-slate-300 transition-colors">
                                        <CopyableId id={device.device_id} />
                                    </TableCell>
                                    <TableCell className="font-medium text-slate-200 group-hover:text-white transition-colors">{device.name || device.display_name || "未命名设备"}</TableCell>
                                    <TableCell>
                                        <Badge variant={statusMeta.variant} className="group-hover:shadow-[0_0_8px_currentColor] transition-shadow">{statusMeta.label}</Badge>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant={onlineStatusMeta.variant} className="group-hover:shadow-[0_0_8px_currentColor] transition-shadow">
                                            <span className={`mr-1.5 h-1.5 w-1.5 rounded-full ${onlineStatusMeta.variant === 'success' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-400'}`}></span>
                                            {onlineStatusMeta.label}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-slate-400 group-hover:text-slate-300 transition-colors" title={formatDateTime(device.last_seen_at)}>
                                        {formatRelativeTime(device.last_seen_at)}
                                    </TableCell>
                                    <TableCell className="text-slate-400 group-hover:text-slate-300 transition-colors">
                                        {formatDateTime(device.created_at).split(' ')[0]} {/* 只展示到日期，悬停可看详细的话可以用 title 或只保留精简信息 */}
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex flex-wrap items-center gap-2 opacity-80 group-hover:opacity-100 transition-opacity">
                                            <Button
                                                type="button"
                                                size="sm"
                                                variant="outline"
                                                className="cursor-pointer"
                                                onClick={() => onViewDetail(device.device_id)}
                                                disabled={isDetailLoading && selectedDeviceId === device.device_id}
                                            >
                                                {isDetailLoading && selectedDeviceId === device.device_id ? (
                                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                ) : (
                                                    <Eye className="mr-2 h-4 w-4" />
                                                )}
                                                查看详情
                                            </Button>
                                            <Button
                                                type="button"
                                                size="sm"
                                                variant="secondary"
                                                className="cursor-pointer"
                                                onClick={() => onPrepareRotate(device.device_id)}
                                            >
                                                轮换
                                            </Button>
                                            <Button
                                                type="button"
                                                size="sm"
                                                variant="destructive"
                                                className="cursor-pointer"
                                                onClick={() => onPrepareDisable(device.device_id)}
                                            >
                                                停用
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>

                <div className="edge-highlight mt-4 flex flex-col gap-3 rounded-xl border border-slate-700/75 bg-slate-900/62 px-3 py-3 text-sm text-slate-300 md:flex-row md:items-center md:justify-between">
                    <div className="flex flex-wrap items-center gap-3">
                        <p>共 {totalDevices} 台设备</p>
                        <p>第 {displayCurrentPage} / {totalPages} 页</p>
                        <label className="flex items-center gap-2">
                            每页显示
                            <select
                                className="rounded border border-slate-700/75 bg-slate-900 px-2 py-1 text-slate-200"
                                value={pageSize}
                                onChange={(event) => onPageSizeChange(Number(event.target.value))}
                            >
                                {PAGE_SIZE_OPTIONS.map((option) => (
                                    <option key={option} value={option}>
                                        {option}
                                    </option>
                                ))}
                            </select>
                        </label>
                    </div>

                    <div className="flex items-center gap-2">
                        <Button type="button" size="sm" variant="outline" disabled={isFetching || displayCurrentPage <= 1} onClick={onFirstPage}>
                            首页
                        </Button>
                        <Button type="button" size="sm" variant="outline" disabled={isFetching || displayCurrentPage <= 1} onClick={onPreviousPage}>
                            上一页
                        </Button>
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={isFetching || displayCurrentPage >= totalPages || totalDevices === 0}
                            onClick={onNextPage}
                        >
                            下一页
                        </Button>
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={isFetching || displayCurrentPage >= totalPages || totalDevices === 0}
                            onClick={onLastPage}
                        >
                            末页
                        </Button>
                        <div className="flex items-center gap-2">
                            <label htmlFor="device-page-jump" className="text-xs text-slate-300">
                                页码
                            </label>
                            <Input
                                id="device-page-jump"
                                type="number"
                                min={1}
                                max={totalPages}
                                value={pageJumpInput}
                                onChange={(event) => onPageJumpInputChange(event.target.value)}
                                className="h-8 w-20"
                            />
                            <Button type="button" size="sm" variant="secondary" disabled={isFetching || totalDevices === 0} onClick={onPageJump}>
                                前往
                            </Button>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
