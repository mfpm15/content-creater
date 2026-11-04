"""Render review stills from a Scene Plan without voice, playback or full encoding."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import opuscar_quality_gate
import video_drafter


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path,help='New directory; existing output is never overwritten')
    parser.add_argument('--aspect',choices=video_drafter.ASPECT_RATIOS,default='9:16')
    parser.add_argument('--style-frames',default='',help='Comma-separated 1-based shot numbers to copy as style-frame-N.png')
    args=parser.parse_args()
    if args.plan.stat().st_size>4_000_000:parser.error('Scene Plan exceeds 4 MB')
    raw=json.loads(args.plan.read_text(encoding='utf-8'))
    plan=video_drafter.normalize_scene_plan(raw,str(raw.get('topic','Opuscar preview')),'',raw['duration'])
    indices=[int(value)-1 for value in args.style_frames.split(',') if value]
    if any(index<0 or index>=len(plan['scenes']) for index in indices):parser.error('Style frame index outside Scene Plan')
    args.output.mkdir(parents=True,exist_ok=False)
    aspect=video_drafter.ASPECT_RATIOS[args.aspect]
    (args.output/'index.html').write_text(video_drafter.generate_composition(plan,aspect,engine='opuscar'),encoding='utf-8')
    (args.output/'scene-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    report=opuscar_quality_gate.inspect(args.output,plan,aspect)
    for index in indices:
        frame=args.output/f'review-frame-{index}.png'
        if frame.is_file():shutil.copyfile(frame,args.output/f'style-frame-{index+1}.png')
    print(json.dumps({'status':report['status'],'frames':len(report['frames']),'issues':report['issues']},ensure_ascii=False))
    return 0 if report['status']=='sampled' else 1


if __name__=='__main__':raise SystemExit(main())
