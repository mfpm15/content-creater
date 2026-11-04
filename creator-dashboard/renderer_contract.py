"""Renderer capabilities shared by planning instructions and pre-render diagnostics.

These checks describe implemented behavior, not semantic/esthetic quality scores.
"""
import json
import re

import opuscar_scene_spec as mechanical
import scene_render

SUBJECTS={'barrier':'barrier','balance':'balance scale','vault':'vault','lock':'lock pins',
    'anchor':'anchor','mast':'mast','prism':'prism','registry':'registry','matrix':'matrix',
    'seal':'seal','bridge':'bridge','wall':'outer wall','aperture':'aperture','sleeve':'sleeve',
    'conduit':'conduit','modules':'modules','plate':'plate','chain':'chain link'}
FAMILIES={'network','journey','device','nature','people','evidence','interface','cityscape','balance','portal','kinetic-type','signal'}
UNSUPPORTED={'process','comparison','constellation','concept'}



def literal_numbers(scene):
    numeric=re.compile(r'(?<![\w.,+−-])[+−-]?\d+(?:[.,]\d+)*(?:\s*%)?')
    return list(dict.fromkeys(numeric.findall(scene.get('onScreenText','')) or numeric.findall(scene.get('narration',''))))


def opuscar_family(scene, family=None):
    family=family or scene.get('visualFamily','')
    if family=='data':return 'data'
    if family in UNSUPPORTED:return 'unsupported'
    if scene.get('type')=='call-to-action' or family=='signal':return 'signal'
    return family if family in FAMILIES else 'unsupported'


def planner_instruction(engine):
    common='\nKONTRAK ENGINE: '+engine+'. Jangan menjanjikan aset eksternal, simulasi fisika, karakter realistis, atau gerak arbitrer dari prosa. Jangan memaksakan topik menjadi objek mekanis yang tidak relevan. Narasi tetap utuh.\n'
    if engine in ('opuscar','threejs'):
        vocabulary={SUBJECTS[obj]:sorted(actions) for obj,actions in mechanical.COMPATIBLE.items()}
        common+='Objek dan aksi mekanis tersedia (gunakan directionSubject/subject dan action yang cocok): '+json.dumps(vocabulary)+'. Nama aksi pada daftar adalah token; tulis arahan dengan verba yang dikenali.\n'
        common+='Jumlah eksplisit 1–12 terutama untuk chain links, weights balance, registry/matrix/modules. Kamera native pakai renderControls.camera: '+', '.join(scene_render.CAMERAS)+'. Lighting/transition juga pakai renderControls; prosa bebas adalah catatan.\n'
        common+=('Opuscar juga memiliki ilustrasi prosedural: '+', '.join(sorted(FAMILIES|{'data'}))+'. Process/comparison/concept/constellation tanpa objek mekanis belum mempunyai diagram native; jangan meminta diagram palsu.\n' if engine=='opuscar' else 'Three.js di luar objek mekanis menampilkan pelat editorial. Jika sengaja memakai teks editorial, nyatakan visualFamily kinetic-type; ini tidak menghasilkan objek/karakter baru.\n')
    elif engine in ('remotion','lottie'):
        common+='Proses/perbandingan perlu diagram eksplisit {kind:process|comparison,labels:[...]}, 2–5 label proses atau tepat 2 label perbandingan, <=48 karakter/label, hanya dari isi naskah.\n'
        common+=('Remotion menampilkan angka literal pada family data; tanpa diagram, scene proses/perbandingan menjadi teks editorial. Tidak ada model 3D atau gambar generatif.\n' if engine=='remotion' else 'Lottie terbatas pada rectangle/ellipse/text/transform; tidak ada narasi audio tertanam atau adegan 3D.\n')
    elif engine=='continuous':
        common+='Hanya konsep trace/focus/assemble yang dipilih pengguna: satu carrier berlanjut, hold dan perubahan bentuk. Bukan ilustrator bebas atau scene 3D. Maksimal 12 beat untuk assemble.\n'
    else:raise ValueError('Engine tidak dikenal')
    return common


def inspect(plan, engine):
    shots=[];errors=[];warnings=[]
    def issue(target,scene,code,message):target.append({'scene':scene,'code':code,'message':message})
    for s in plan['scenes']:
        key=s['id'];family=s.get('visualFamily','');mode='editorial'
        if engine in ('opuscar','threejs'):
            spec=mechanical.interpret(s)
            if spec:
                mode='mechanical:'+spec['object']
                for reason in spec['issues']:issue(errors,key,'unsupported_mechanical_direction',reason)
            elif engine=='opuscar':
                mode=opuscar_family(s)
                if mode=='data' and not literal_numbers(s):issue(warnings,key,'missing_literal_metric','Scene data tidak memiliki angka literal; renderer tidak akan mengarang angka. Perbaiki judul atau keluarga visual.')
                if mode=='unsupported':issue(errors,key,'unsupported_visual','Visual belum memiliki implementasi Opuscar; pilih objek/keluarga yang didukung atau perbaiki scene.')
            elif family!='kinetic-type':
                issue(warnings,key,'editorial_fallback','Three.js akan memakai pelat editorial, bukan objek yang diminta. Pilih objek yang didukung atau tandai kinetic-type jika disengaja.')
        elif engine in ('remotion','lottie'):
            if s.get('diagram'):mode='diagram:'+s['diagram']['kind']
            elif family in ('process','comparison'):
                issue(warnings,key,'missing_diagram_labels','Belum ada diagram berlabel; isi diagram dengan label dari naskah sebelum mengharapkan visual proses/perbandingan.')
            elif engine=='remotion' and family=='data':
                mode='literal_metrics' if any(len(n)<=30 for n in literal_numbers(s)) else 'editorial'
                if mode=='editorial':issue(warnings,key,'missing_literal_metric','Tidak ada angka literal yang dapat ditampilkan; Remotion memakai teks editorial.')
            elif engine=='lottie':mode='vector_primitives'
        elif engine=='continuous':
            concept=plan.get('motionDesign',{}).get('concept','unspecified');mode='continuous:'+concept
            if concept not in ('trace','focus','assemble'):issue(errors,key,'missing_continuous_concept','Pilih konsep trace/focus/assemble sebelum merender Continuous Motion.')
            elif concept=='assemble' and len(plan['scenes'])>12:issue(errors,key,'assemble_beat_limit','Assemble mendukung maksimal 12 beat.')
        else:raise ValueError('Engine tidak dikenal')
        shots.append({'scene':key,'renderMode':mode})
    return {'version':1,'engine':engine,'status':'needs_revision' if errors else 'review_warnings' if warnings else 'supported',
        'errors':errors,'warnings':warnings,'shots':shots,'scope':'Known renderer coverage only; not semantic or aesthetic validation.'}


def verify(plan, engine):
    report=inspect(plan,engine)
    if report['errors']:
        raise ValueError('Rencana belum dapat dirender: '+'; '.join(x['scene']+': '+x['message'] for x in report['errors'][:3]))
    return report
