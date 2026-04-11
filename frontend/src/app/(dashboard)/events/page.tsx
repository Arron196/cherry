"use client";

import { useState } from "react";
import { format } from "date-fns";
import { ChevronLeft, ChevronRight, Search, Workflow } from "lucide-react";
import { useEvents } from "@/hooks/use-queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { t } from "@/lib/translations";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

export default function EventsPage() {
    const [page, setPage] = useState(0);
    const [batchId, setBatchId] = useState("");
    const [deviceId, setDeviceId] = useState("");
    const limit = 20;

    const { data, isLoading, isError } = useEvents({
        limit,
        offset: page * limit,
        batch_id: batchId || undefined,
        device_id: deviceId || undefined,
    });

    const totalPages = Math.max(1, Math.ceil((data?.total || 0) / limit));

    return (
        <div className="space-y-7">
            <section className="panel-shell edge-highlight p-5 md:p-6">
                <div className="flex items-center gap-3">
                    <span className="edge-highlight inline-flex h-10 w-10 items-center justify-center rounded-xl border border-primary-300/35 bg-primary-500/24 text-primary-100">
                        <Workflow className="h-5 w-5" />
                    </span>
                    <div>
                        <h1 className="display-heading text-2xl font-semibold tracking-tight text-slate-100 md:text-3xl">事件列表</h1>
                        <p className="mt-1 text-sm text-slate-300">支持按批次和设备检索，快速定位链路异常。</p>
                    </div>
                </div>
            </section>

            <Card className="panel-shell edge-highlight">
                <CardHeader>
                    <CardTitle className="display-heading">筛选条件</CardTitle>
                </CardHeader>
                <CardContent>
                    <form
                        className="grid gap-3 sm:grid-cols-3"
                        onSubmit={(event) => {
                            event.preventDefault();
                            setPage(0);
                        }}
                    >
                        <div className="space-y-1">
                            <label className="text-sm text-slate-200" htmlFor="events-batch-id-filter">
                                批次 ID
                            </label>
                            <Input
                                id="events-batch-id-filter"
                                placeholder="按批次 ID 过滤"
                                value={batchId}
                                onChange={(event) => setBatchId(event.target.value)}
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-sm text-slate-200" htmlFor="events-device-id-filter">
                                设备 ID
                            </label>
                            <Input
                                id="events-device-id-filter"
                                placeholder="按设备 ID 过滤"
                                value={deviceId}
                                onChange={(event) => setDeviceId(event.target.value)}
                            />
                        </div>
                        <Button type="submit" className="sm:w-auto">
                            <Search className="mr-2 h-4 w-4" />
                            查询
                        </Button>
                    </form>
                </CardContent>
            </Card>

            <Card className="panel-shell edge-highlight">
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>事件 ID</TableHead>
                                <TableHead>批次 ID</TableHead>
                                <TableHead>设备 ID</TableHead>
                                <TableHead>时间</TableHead>
                                <TableHead>状态</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {isLoading && (
                                <TableRow>
                                    <TableCell colSpan={5} className="text-center text-slate-300">
                                        正在加载事件数据...
                                    </TableCell>
                                </TableRow>
                            )}
                            {isError && (
                                <TableRow>
                                    <TableCell colSpan={5} className="text-center text-red-300">
                                        事件数据加载失败，请稍后重试
                                    </TableCell>
                                </TableRow>
                            )}
                            {data?.items.map((item) => (
                                <TableRow key={item.id}>
                                    <TableCell>{item.id}</TableCell>
                                    <TableCell>{item.batch_id}</TableCell>
                                    <TableCell>{item.device_id}</TableCell>
                                    <TableCell>{format(new Date(item.timestamp), "yyyy-MM-dd HH:mm:ss")}</TableCell>
                                    <TableCell>
                                        <Badge
                                            variant={
                                                item.ingest_status === "ANCHORED"
                                                    ? "success"
                                                    : item.ingest_status === "DEAD_LETTER"
                                                        ? "destructive"
                                                        : item.ingest_status === "FAILED_RETRYING"
                                                            ? "warning"
                                                            : "secondary"
                                            }
                                        >
                                            {t(item.ingest_status)}
                                        </Badge>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {data?.items.length === 0 && !isLoading && (
                                <TableRow>
                                    <TableCell colSpan={5} className="text-center text-slate-300">
                                        暂无符合条件的事件
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>

                    <div className="edge-highlight mt-3 flex flex-col items-start gap-2 rounded-xl border border-slate-700/75 bg-slate-900/62 px-3 py-3 sm:flex-row sm:items-center sm:justify-end">
                        <div className="text-xs text-slate-300">第 {page + 1} / {totalPages} 页</div>
                        <div className="flex items-center gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                aria-label="上一页"
                                onClick={() => setPage((prev) => Math.max(0, prev - 1))}
                                disabled={page === 0 || isLoading}
                            >
                                <ChevronLeft className="h-4 w-4" />
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                aria-label="下一页"
                                onClick={() => setPage((prev) => prev + 1)}
                                disabled={!data || (page + 1) * limit >= data.total || isLoading}
                            >
                                <ChevronRight className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
