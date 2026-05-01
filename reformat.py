import re

with open('frontend/src/app/(dashboard)/batches/[id]/page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Header and set up the grid
new_header = '''        <div className="mx-auto max-w-6xl space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4 pb-2">
                <Button variant="outline" size="sm" className="h-10 gap-1 rounded-full px-4 border-slate-700/70 text-slate-300 hover:text-white bg-slate-800/50 hover:bg-slate-700 transition-colors" asChild>
                    <Link href="/batches">
                        <ArrowLeft className="h-4 w-4 mr-1" />
                        <span>返回</span>
                    </Link>
                </Button>
                <div>
                    <h1 className="display-heading text-2xl font-semibold tracking-tight text-white md:text-3xl">
                        批次详情
                    </h1>
                    <div className="flex items-center gap-2 text-sm text-slate-300 mt-1.5">
                        <span className="font-semibold text-slate-200">批次 ID：</span>
                        <code className="edge-highlight rounded-md border border-slate-700/70 bg-slate-900/72 px-2 py-0.5 font-mono text-sm">{trace.batch_id}</code>
                    </div>
                </div>
            </div>

            {/* Supply Chain Stage Progress Bar */}'''

content = re.sub(
    r'        <div className="mx-auto max-w-5xl space-y-7">\n.*?\{\/\* Header \*\/\}.*?<\/section>\n\n\s*\{\/\* Supply Chain Stage Progress Bar \*\/\}',
    new_header,
    content,
    flags=re.DOTALL
)

grid_start = '''            </motion.div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Column */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Sensor History Multi-Axis Chart */}'''

content = content.replace('            </motion.div>\n\n            {/* Sensor History Multi-Axis Chart */}', grid_start)
content = content.replace('            </motion.div>\r\n\r\n            {/* Sensor History Multi-Axis Chart */}', grid_start)

# Move Quality Panel to Right Column
quality_pattern = r'            \{\/\* Quality Assessment Panel \*\/\}[\s\S]*?<\/motion\.div>\n\s*\}\)'
q_match = re.search(quality_pattern, content)
if q_match:
    quality_block = q_match.group(0)
    # remove quality from current position
    content = content.replace(quality_block + '\n\n', '')
    content = content.replace(quality_block + '\r\n\r\n', '')
    
    # insert right column after Event Timeline
    timeline_end_pattern = r'            \{\/\* Event Timeline \*\/\}[\s\S]*?<\/motion\.div>'
    t_match = re.search(timeline_end_pattern, content)
    if t_match:
        timeline_block = t_match.group(0)
        
        new_structure = timeline_block + '''
                </div>
                
                {/* Right Column */}
                <div className="space-y-6">
                    ''' + quality_block + '''
                </div>
            </div>'''
        
        content = content.replace(timeline_block, new_structure)

with open('frontend/src/app/(dashboard)/batches/[id]/page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Re-layout completed successfully.')