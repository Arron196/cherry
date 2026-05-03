import re
import os

files = [
    'frontend/src/app/(dashboard)/batches/[id]/page.tsx',
    'frontend/src/app/(dashboard)/trace/[id]/page.tsx'
]

for path in files:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Increase the container widths
        content = re.sub(r'max-w-5xl', 'max-w-[1600px] w-full', content)
        content = re.sub(r'max-w-6xl', 'max-w-[1600px] w-full', content)
        content = re.sub(r'max-w-4xl', 'max-w-[1600px] w-full', content)
        content = re.sub(r'max-w-3xl', 'max-w-[1600px] w-full', content)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Updated {path}')
    else:
        print(f'Not found {path}')
