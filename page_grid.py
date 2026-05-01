import re

with open('frontend/src/app/(dashboard)/page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

new_layout = '''            {/* High visual features section */}
            <motion.div custom={6} variants={fadeIn} initial="hidden" animate="visible" className="grid gap-6 xl:grid-cols-3">
                <div className="xl:col-span-3">
                    <SupplyChainMap />
                </div>
                <div className="xl:col-span-2">
                    <SensorCharts />
                </div>
                <div className="xl:col-span-1">
                    <BlockchainLedger />
                </div>
            </motion.div>'''

content = re.sub(r'            \{\/\* High visual features section \*\/\}[\s\S]*?<\/motion\.div>', new_layout, content)

with open('frontend/src/app/(dashboard)/page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
