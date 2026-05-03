import re

with open('frontend/src/app/(dashboard)/page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Make the layout wider and more modern
content = re.sub(
    r'return \(\s*<div className="space-y-7">',
    'return (\n        <div className="max-w-[1600px] mx-auto w-full space-y-8 pb-8 px-4 md:px-8">',
    content
)

# Rewrite the header
new_header = '''            <motion.section
                custom={0}
                variants={fadeIn}
                initial="hidden"
                animate="visible"
                className="panel-shell edge-highlight relative overflow-hidden rounded-2xl border border-slate-700/60 bg-gradient-to-br from-slate-900/90 to-slate-800/90 p-8 md:p-10 shadow-2xl backdrop-blur-md"
            >
                <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary-500/20 blur-3xl animate-[aurora-shift_14s_ease-in-out_infinite]" />
                <div className="pointer-events-none absolute -left-16 bottom-[-76px] h-56 w-56 rounded-full bg-cyan-400/20 blur-3xl animate-[aurora-shift_18s_ease-in-out_infinite]" />
                <div className="relative flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
                    <div className="space-y-3">
                        <div className="flex items-center gap-3">
                            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-500/20 border border-primary-500/30 text-primary-400 shadow-[0_0_15px_rgba(16,185,129,0.3)]">
                                <Activity className="h-6 w-6" />
                            </div>
                            <h1 className="text-3xl font-bold tracking-tight text-white md:text-4xl">
                                供应全链路态势感知
                            </h1>
                        </div>
                        <p className="text-slate-400 max-w-2xl text-sm md:text-base leading-relaxed">
                            实时监控农产品全生命周期的温湿度指标、品质评级与区块链防伪溯源事件，随时掌握资产流转。
                        </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                        <Link href="/events" className="inline-flex">
                            <Button size="lg" className="h-11 rounded-full px-6 font-medium shadow-lg hover:shadow-primary-500/25 transition-all">
                                事件流汇总
                                <ArrowRight className="ml-2 h-4 w-4" />
                            </Button>
                        </Link>
                        <Link href="/alerts" className="inline-flex">
                            <Button size="lg" variant="outline" className="h-11 rounded-full px-6 border-slate-600 bg-slate-800/50 hover:bg-slate-700/50 font-medium text-slate-200 transition-all">
                                告警处理中心
                            </Button>
                        </Link>
                    </div>
                </div>
                
                <div className="mt-8 flex flex-wrap items-center gap-3 border-t border-slate-700/60 pt-6 relative z-10">
                    <div className="flex items-center gap-2 rounded-full border border-slate-700/80 bg-slate-900/60 px-3 py-1.5 shadow-inner">
                        <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
                        <span className="text-xs font-medium text-slate-300">本月事件流：<span className="text-white">{overview?.total_events ?? "--"}</span> 笔</span>
                    </div>
                    <div className="ml-auto text-xs text-slate-400 flex items-center gap-1.5">
                        <Radio className="h-3.5 w-3.5" />
                        <span className="text-slate-300 font-medium">数据最后更新：{recentEventTime}</span>
                    </div>
                </div>
            </motion.section>'''

# Replace old header
content = re.sub(
    r'<motion\.section[\s\S]*?<\/motion\.section>',
    new_header,
    content,
    count=1
)

with open('frontend/src/app/(dashboard)/page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Dashboard header rewritten')

