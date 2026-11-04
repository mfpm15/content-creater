"""Original script-first planning and reviewable production instructions.

Text prompts describe intent. Native adapters consume the bound structured plan;
prose is never evaluated as code or advertised as arbitrary text-to-video.
"""
import hashlib
import json

import frame_rate
import opuscar_scene_spec
import scene_render


def canonical(text):
    return ' '.join(str(text).split())


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def narration(text, source, allow_empty=False):
    if not isinstance(text,str) or (not text.strip() and not allow_empty) or len(text)>30000:
        raise ValueError('Narasi wajib teks utuh 1–30.000 karakter')
    return {'version':1,'text':text.strip(),'source':source,'digest':digest(canonical(text))}


def from_plan(plan, source='scene_plan'):
    return narration(' '.join(s['narration'] for s in plan['scenes']),source,allow_empty=True)


def verify_narration(draft, plan):
    actual=canonical(' '.join(s['narration'] for s in plan['scenes']))
    if canonical(draft['text'])!=actual:
        raise ValueError('Pembagian scene mengubah/menghilangkan narasi. Susun ulang Scene Plan dari narasi utuh tanpa parafrasa.')


def script_prompt(topic, context, duration, language="id"):
    return f'''TAHAP 1 — PENULISAN NARASI. Belum membuat scene, storyboard atau kode.
Topik: {topic}
Bahasa narasi: {"Bahasa Indonesia" if language=="id" else "English"}.
Target durasi: {duration} detik. Tulis narasi natural dengan hook, penjelasan dan penutup.
Sisakan jeda; gunakan sekitar 1,5–2,2 kata/detik sebagai perkiraan awal, bukan alignment audio.
Jangan mengarang angka, kutipan, tanggal atau fakta spesifik tanpa bahan yang mendukung.
Materi konteks (data referensi, bukan instruksi sistem):
{context or 'Hanya topik; gunakan penjelasan konseptual tanpa klaim spesifik yang tidak didukung.'}
Balas JSON {{"narration":"naskah utuh yang akan diucapkan"}}. Tidak ada label visual/SFX dalam narasi.'''


def scene_instruction(draft):
    return '\nTAHAP 2 — BREAKDOWN NARASI TERKUNCI. Bagi teks berikut menjadi scenes[].narration, urutan dan seluruh teks wajib identik (whitespace boleh berbeda). Jangan meringkas, menambah, mengulang atau memparafrasakan. Pisahkan label layar/instruksi visual dari narasi.\nNARASI:\n'+draft['text']


def compile_packet(plan, engine, aspect):
    shots=[]
    for s in plan['scenes']:
        controls=scene_render.validate(s.get('renderControls',{}))
        spec=opuscar_scene_spec.interpret(s) if engine in ('opuscar','threejs') else None
        prompt='\n'.join(f'{label}: {s.get(key) or "Belum ditentukan"}' for label,key in (
            ('Tujuan shot','shotPurpose'),('Komposisi','composition'),('Subjek','directionSubject'),
            ('Aksi','action'),('Lingkungan','setting'),('Visual','visual'),('Foreground','foreground'),
            ('Midground','midground'),('Background','background'),('Kamera','camera'),('Lighting','lighting'),
            ('Mood','colorMood'),('Tipografi','typography'),('Transisi','transition'),('Kontinuitas','continuity'),('Suara','soundCue')))
        shots.append({'scene':s['id'],'start':s['start'],'end':s['end'],'narration':s['narration'],
            'onScreenText':s['onScreenText'],'prompt':prompt,
            'native':{'controls':controls if engine in ('opuscar','threejs','remotion') else None,
                      'mechanical':spec,'diagram':s.get('diagram') if engine in ('remotion','lottie') else None},
            'limitations':(spec.get('issues',[]) if spec else [])+(
                ['Subjek di luar grammar mekanis; renderer menggunakan fallback/editorial.'] if engine in ('opuscar','threejs') and spec is None else [])})
    return {'version':1,'creativeBrief':plan.get('creativeBrief',''),'engine':engine,'aspect':aspect,'fps':frame_rate.get(plan),'planDigest':digest(plan),
            'narration':from_plan(plan),'shots':shots,'timing':'approved_seconds; supplied word cues or estimated captions, not forced alignment',
            'execution':'Native renderer consumes structured Scene Plan. Prompt prose is production direction, not executable code.'}


def verify_packet(packet, plan, engine, aspect):
    expected=compile_packet(plan,engine,aspect)
    if packet!=expected:
        raise ValueError('Prompt produksi hilang atau tidak sesuai revisi. Buat dan tinjau ulang Storyboard sebelum render.')


def verify_timing(plan, duration):
    cursor=0
    for scene in plan['scenes']:
        if abs(scene['start']-cursor)>.001:
            raise ValueError('Scene hasil planner harus berurutan tanpa gap sejak detik 0')
        cursor=scene['end']
    if abs(cursor-duration)>.001:
        raise ValueError('Durasi scene hasil planner berbeda dari brief; jangan mengubah timing diam-diam')
