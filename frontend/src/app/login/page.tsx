"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/hooks/use-auth";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ArrowRight, CheckCircle2, ShieldCheck } from "lucide-react";
import { Services } from "@/lib/services";

export default function LoginPage() {
    const router = useRouter();
    const { login } = useAuthStore();
    const [username, setUsername] = useState("admin");
    const [password, setPassword] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const demoHint = "admin / admin123（管理员） 或 regulator / regulator123（监管员）";

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setErrorMessage(null);

        const normalized = username.trim().toLowerCase();
        if (!normalized) {
            setErrorMessage("请输入用户名。可使用 admin 或 regulator。");
            setIsLoading(false);
            return;
        }

        if (!password.trim()) {
            setErrorMessage("请输入密码。演示环境可输入任意内容。");
            setIsLoading(false);
            return;
        }

        try {
            const loginResponse = await Services.login({
                username: normalized,
                password,
            });
            login(loginResponse.access_token, loginResponse.role);
            router.push("/");
        } catch (error) {
            const detail = typeof error === "object" && error !== null && "detail" in error ? String((error as { detail: unknown }).detail) : "登录失败，请检查账号密码后重试。";
            setErrorMessage(detail);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="relative h-screen w-full overflow-y-auto">
            <div className="relative flex min-h-full items-center justify-center p-4 md:p-8">
                <div aria-hidden className="pointer-events-none absolute inset-0">
                <div className="absolute left-[-8rem] top-[-5rem] h-80 w-80 rounded-full bg-primary-500/24 blur-[110px]" />
                <div className="absolute bottom-[-7rem] right-[-4rem] h-72 w-72 rounded-full bg-cyan-400/20 blur-[100px]" />
            </div>
            <div className="panel-shell edge-highlight relative grid w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-700/80 bg-slate-900/88 md:grid-cols-[1.2fr_1fr]">
                <section className="accent-grid hidden flex-col justify-between border-r border-slate-700/80 bg-gradient-to-b from-slate-900/90 via-slate-900/55 to-primary-900/30 p-8 md:flex">
                    <div>
                        <div className="edge-highlight inline-flex items-center gap-2 rounded-full border border-primary-300/35 bg-primary-500/20 px-3 py-1 text-xs text-primary-100">
                            <ShieldCheck className="h-4 w-4" />
                            可信溯源控制台
                        </div>
                        <h1 className="display-heading mt-5 text-3xl font-semibold tracking-tight text-slate-100">
                            Cherry Trace
                        </h1>
                        <p className="mt-3 max-w-md text-sm leading-6 text-slate-200">
                            从设备采集、事件追踪到区块链锚定，统一在一个界面完成监管、告警与质量分析。
                        </p>
                    </div>
                    <div className="space-y-3">
                        {["实时事件流可视化", "批次级可追溯链路", "异常告警闭环处理"].map((item) => (
                            <div key={item} className="edge-highlight flex items-center gap-2 rounded-lg border border-slate-700/70 bg-slate-900/42 px-2.5 py-1.5 text-sm text-slate-100">
                                <CheckCircle2 className="h-4 w-4 text-primary-300" />
                                <span>{item}</span>
                            </div>
                        ))}
                    </div>
                </section>

                <section className="p-5 sm:p-8">
                    <Card className="border-none bg-transparent shadow-none">
                        <CardHeader className="space-y-2 px-0 pt-0">
                            <div className="edge-highlight mb-2 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary-300 via-accent-teal to-accent-gold shadow-[0_18px_36px_-22px_rgba(34,211,238,0.82)] md:hidden">
                                <ShieldCheck className="h-5 w-5 text-slate-950" />
                            </div>
                            <CardTitle className="display-heading text-2xl text-slate-100">欢迎登录</CardTitle>
                            <CardDescription>登录 Cherry Trace 溯源控制台</CardDescription>
                        </CardHeader>
                        <CardContent className="px-0 pb-0">
                            <form onSubmit={handleLogin} className="space-y-4">
                                <div className="space-y-2">
                                    <label htmlFor="username" className="text-sm font-medium text-slate-200">
                                        用户名
                                    </label>
                                    <Input
                                        id="username"
                                        type="text"
                                        placeholder="请输入用户名"
                                        value={username}
                                        onChange={(e) => setUsername(e.target.value)}
                                        required
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label htmlFor="password" className="text-sm font-medium text-slate-200">
                                        密码
                                    </label>
                                    <Input
                                        id="password"
                                        type="password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        placeholder="请输入密码"
                                        required
                                    />
                                </div>
                                {errorMessage && (
                                    <div className="rounded-lg border border-rose-300/45 bg-rose-700/30 px-3 py-2 text-sm text-rose-100" role="status" aria-live="polite">
                                        {errorMessage}
                                    </div>
                                )}
                                <Button className="w-full" type="submit" loading={isLoading}>
                                    登录系统
                                    <ArrowRight className="ml-1.5 h-4 w-4" />
                                </Button>
                                <div className="edge-highlight rounded-lg border border-slate-700/75 bg-slate-800/72 px-3 py-2 text-xs text-slate-300">
                                    <p>演示账号：</p>
                                    <p className="mt-0.5 text-slate-100">{demoHint}</p>
                                </div>
                            </form>
                        </CardContent>
                    </Card>
                </section>
            </div>
            </div>
        </div>
    );
}
