"""Deterministic local diagram layout, SVG and PNG from one bounded specification."""
import html
import os
import textwrap
from pathlib import Path


def render(kind: str, labels: list[str], svg: Path, png: Path) -> dict:
    if kind not in {'flow','mindmap'} or not isinstance(labels,list) or not 2<=len(labels)<=30 or any(not isinstance(s,str) or not s.strip() or len(s)>60 for s in labels):
        raise ValueError('Diagram flow/mindmap memerlukan 2–30 label, maksimal 60 karakter per label')
    try: from PIL import Image, ImageDraw, ImageFont
    except ImportError: raise ValueError('Diagram PNG memerlukan dependency opsional Pillow') from None
    width,height=1200, max(500,len(labels)*110+60)
    image=Image.new('RGB',(width,height),'white');draw=ImageDraw.Draw(image)
    try: font=ImageFont.truetype(os.getenv('ARTICLE_DIAGRAM_FONT','DejaVuSans.ttf'),22)
    except OSError: font=ImageFont.load_default()
    nodes=[]
    for i,label in enumerate(labels):
        x,y=(250,30+i*110) if kind=='flow' else ((40,height//2-40) if i==0 else (500,30+(i-1)*110))
        nodes.append((x,y,700 if kind=='flow' else (320 if i==0 else 600),80,label))
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="white"/>']
    for i,(x,y,w,h,label) in enumerate(nodes):
        if i:
            a=nodes[i-1] if kind=='flow' else nodes[0]
            start=(a[0]+a[2]//2,a[1]+a[3]) if kind=='flow' else (a[0]+a[2],a[1]+a[3]//2)
            end=(x+w//2,y) if kind=='flow' else (x,y+h//2)
            draw.line([start,end],fill='#334155',width=3);parts.append(f'<path d="M{start[0]} {start[1]} L{end[0]} {end[1]}" fill="none" stroke="#334155" stroke-width="3"/>')
        draw.rounded_rectangle((x,y,x+w,y+h),radius=8,fill='#eff6ff',outline='#334155',width=2)
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#eff6ff" stroke="#334155"/>')
        for j,line in enumerate(textwrap.wrap(label,width=max(12,w//15))[:3]):
            draw.text((x+15,y+8+j*23),line,font=font,fill='#0f172a')
            parts.append(f'<text x="{x+15}" y="{y+28+j*23}" font-family="sans-serif" font-size="22">{html.escape(line)}</text>')
    parts.append('</svg>');svg.parent.mkdir(parents=True,exist_ok=True)
    svg.write_text('\n'.join(parts),'utf-8');image.save(png)
    return {'width':width,'height':height,'kind':kind,'nodes':len(nodes)}
