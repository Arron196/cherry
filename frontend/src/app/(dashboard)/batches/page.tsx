"use client";

import { useState } from "react";
import { format } from "date-fns";
import { ChevronLeft, ChevronRight, Eye, PackageSearch, Search } from "lucide-react";
import Link from "next/link";
import { useBatches } from "@/hooks/use-queries";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

export default function BatchesPage() {
    const [page, setPage] = useState(0);
    const [deviceId, setDeviceId] = useState("");
    const limit = 20;

    const { data, isLoading, isError } = useBatches({
        limit,
        offset: page * limit,
        device_id: deviceId || undefined,
    });

    const totalPages = Math.max(1, Math.ceil((data?.total || 0) / limit));

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        setPage(0);
    };

    return (
        <div className="space-y-7">
            <section className="panel-shell edge-highlight p-5 md:p-6">
                <div className="flex items-center gap-3">
                    <span className="edge-highlight inline-flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-300/35 bg-cyan-500/22 text-cyan-100">
                        <PackageSearch className="h-5 w-5" />
                    </span>
                    <div>
                        <h1 className="display-heading text-2xl font-semibold tracking-tight text-slate-100 md:text-3xl">批次列表</h1>
                        <p className="mt-1 text-sm text-slate-300">从批次维度查看采集规模、时间范围与追踪入口。</p>
                    </div>
                </div>
            </section>

            <Card className="panel-shell edge-highlight">
                <CardHeader>
                    <CardTitle className="display-heading">筛选条件</CardTitle>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSearch} className="flex flex-col gap-3 sm:flex-row sm:items-center">
                        <div className="w-full space-y-1 sm:max-w-sm">
                            <label className="text-sm text-slate-200" htmlFor="batches-device-id-filter">
                                设备 ID
                            </label>
                            <Input
                                id="batches-device-id-filter"
                                placeholder="按设备 ID 过滤"
                                value={deviceId}
                                onChange={(e) => setDeviceId(e.target.value)}
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
                            <TableRow className="hover:bg-slate-800/55 data-[state=selected]:bg-slate-800/70">
                                <TableHead>批次 ID</TableHead>
                                <TableHead>设备 ID</TableHead>
                                <TableHead>事件数</TableHead>
                                <TableHead>开始时间</TableHead>
                                <TableHead>结束时间</TableHead>
                                <TableHead>操作</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {isLoading && (
                                <TableRow>
                                    <TableCell colSpan={6} className="text-center text-slate-300">
                                        正在加载批次数据...
                                    </TableCell>
                                </TableRow>
                            )}
                            {isError && (
                                <TableRow>
                                    <TableCell colSpan={6} className="text-center text-red-300">
                                        批次数据加载失败，请稍后重试
                                    </TableCell>
                                </TableRow>
                            )}
                            {data?.items.map((batch) => (
                                <TableRow key={batch.batch_id}>
                                    <TableCell className="font-medium text-slate-100">{batch.batch_id}</TableCell>
                                    <TableCell className="text-slate-200">{batch.device_id}</TableCell>
                                    <TableCell className="text-slate-200">{batch.event_count}</TableCell>
                                    <TableCell className="text-slate-200">
                                        {format(new Date(batch.start_time), "yyyy-MM-dd HH:mm:ss")}
                                    </TableCell>
                                    <TableCell className="text-slate-200">
                                        {batch.end_time 
                                            ? format(new Date(batch.end_time), "yyyy-MM-dd HH:mm:ss") 
                                            : <span className="text-slate-500">进行中</span>}
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-1">
                                            <Link
                                                href={`/batches/${batch.batch_id}`}
                                                className={cn(
                                                    buttonVariants({ variant: "ghost", size: "sm" }),
                                                    "cursor-pointer hover:bg-primary-500/20 hover:text-primary-100"
                                                    )}
                                            >
                                                <Eye className="mr-1 h-4 w-4" />
                                                详情
                                            </Link>
                                            <Link
                                                href={`/trace/${batch.batch_id}`}
                                                className={cn(
                                                    buttonVariants({ variant: "ghost", size: "sm" }),
                                                    "cursor-pointer hover:bg-primary-500/20 hover:text-primary-100"
                                                    )}
                                            >
                                                溯源
                                            </Link>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {data?.items.length === 0 && !isLoading && (
                                <TableRow>
                                    <TableCell colSpan={6} className="text-center text-slate-300">
                                        暂无符合条件的批次
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
