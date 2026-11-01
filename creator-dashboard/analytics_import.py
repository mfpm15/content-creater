"""User-mapped CSV imports; no guessed Instagram/TikTok schemas."""
import csv
import io
import math

import youtube_analytics as ya

METRICS = {'views','likes','comments','shares','average_watch_seconds','completion_percent'}


def inspect_csv(text: str) -> dict:
    if len(text.encode('utf-8')) > ya.MAX_CSV_BYTES: raise ValueError('CSV melebihi 2 MB')
    try: dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t')
    except csv.Error: dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')), dialect=dialect)
    headers = reader.fieldnames or []
    if not headers or len(headers)>100 or len(set(headers)) != len(headers): raise ValueError('Header kosong, duplikat, atau terlalu banyak')
    rows=[]
    for index,row in enumerate(reader):
        if index>=10000: raise ValueError('CSV melebihi 10.000 baris')
        if None in row or any(value is None for value in row.values()):raise ValueError('Jumlah kolom CSV tidak konsisten')
        rows.append(row)
    return {'headers':headers,'rows':rows,'preview':rows[:5],'row_count':len(rows)}


def mapped_import(text: str, platform: str, mapping: dict, units: str = 'percent', scenes: list | None = None) -> dict:
    if platform not in {'youtube','reels','tiktok'} or not isinstance(mapping,dict): raise ValueError('Platform/pemetaan tidak valid')
    if set(mapping)-METRICS-{'time','retention','video_id'}:raise ValueError('Nama metrik pemetaan tidak dikenal')
    data=inspect_csv(text)
    if bool(mapping.get('time')) != bool(mapping.get('retention')): raise ValueError('Pilih kolom waktu dan retensi bersama')
    if not mapping.get('time') and not any(mapping.get(k) for k in METRICS): raise ValueError('Pilih metrik yang ingin dianalisis')
    for column in mapping.values():
        if column and (not isinstance(column,str) or column not in data['headers']): raise ValueError('Kolom pemetaan tidak ditemukan')
    if mapping.get('time') and mapping.get('retention'):
        target=io.StringIO(); writer=csv.writer(target); writer.writerow(['time','retention'])
        for row in data['rows']: writer.writerow([row.get(mapping['time']),row.get(mapping['retention'])])
        result=ya.analyze_retention(target.getvalue().encode(), units=units)
        if scenes: result['scenes']=scene_retention(result['points'],result['events'],scenes)
    else:
        normalized=[]; skipped=0
        for row in data['rows']:
            item={}
            for metric in METRICS:
                if mapping.get(metric):
                    number=ya._number(row.get(mapping[metric]))
                    if number is not None and number>=0 and (metric!='completion_percent' or number<=100): item[metric]=number
            if not item: skipped+=1; continue
            item['video_id']=str(row.get(mapping.get('video_id',''),'') or '')[:128]
            normalized.append(item)
        result={'records':normalized,'invalid_rows':skipped}
    used={v for v in mapping.values() if v}
    return {**result,'platform':platform,'schema':'user_mapped_unverified_native_export','unused_columns':[h for h in data['headers'] if h not in used]}


def scene_retention(points: list, events: list, scenes: list) -> list:
    if not isinstance(scenes,list) or len(scenes)>200: raise ValueError('Daftar scene tidak valid')
    output=[]; previous=0
    for index,scene in enumerate(scenes):
        if not isinstance(scene,dict): raise ValueError('Scene harus objek')
        try:start,end=float(scene['start']),float(scene['end'])
        except (KeyError,TypeError,ValueError):raise ValueError('Scene memerlukan start/end numerik') from None
        if not math.isfinite(start+end) or start<previous or end<=start: raise ValueError('Rentang scene tidak valid/tumpang tindih')
        previous=end
        samples=[p for p in points if start<=p['second']<end]
        output.append({'scene':str(scene.get('id',index+1))[:128],'start':start,'end':end,'samples':len(samples),
                       'average_sample_retention':round(sum(p['retention'] for p in samples)/len(samples),2) if samples else None,
                       'events':[e for e in events if start<=e['second']<end]})
    return output
