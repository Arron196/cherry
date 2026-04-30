import re

with open('article/frontend_figures/renderers.mjs', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(
    r'const\s+COLORS\s*=\s*\{[^}]*\};', 
    '''const COLORS = {
    paper: "#ffffff",
    panel: "#ffffff",
    ink: "#212529",
    muted: "#6c757d",
    border: "#ced4da",
    grid: "#e9ecef",
    cherry: "#000000",
    navy: "#212529",
    teal: "#343a40",
    sage: "#495057",
    gold: "#495057",
    plum: "#495057",
    blueSoft: "#f8f9fa",
    tealSoft: "#e9ecef",
    greenSoft: "#f8f9fa",
    amberSoft: "#e9ecef",
    roseSoft: "#f8f9fa",
    lilacSoft: "#e9ecef",
    sandSoft: "#f8f9fa",
    white: "#ffffff",
    success: "#212529",
    warning: "#495057",
    danger: "#212529",
};''', 
    text, 
    count=1
)

text = re.sub(
    r'const\s+FONT_HEAD\s*=\s*\'[^;]+;', 
    '''const FONT_HEAD = '"Times New Roman", Times, serif';''', 
    text, count=1
)
text = re.sub(
    r'const\s+FONT_SANS\s*=\s*\'[^;]+;', 
    '''const FONT_SANS = 'Arial, Helvetica, sans-serif';''', 
    text, count=1
)
text = re.sub(
    r'const\s+FONT_MONO\s*=\s*\'[^;]+;', 
    '''const FONT_MONO = '"Courier New", Courier, monospace';''', 
    text, count=1
)

# Remove rx, ry to square corners
text = re.sub(r'rx="[0-9]+"', 'rx="0"', text)
text = re.sub(r'ry="[0-9]+"', 'ry="0"', text)

# Remove shadow filter
text = re.sub(r'<filter\s+id="dropShadow"[^>]*>.*?</filter>', '', text, flags=re.DOTALL)
text = re.sub(r'\s*filter="url\(#dropShadow\)"', '', text)

with open('article/frontend_figures/renderers.mjs', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated style constants in renderers.mjs")
