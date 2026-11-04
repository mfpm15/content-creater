"""Bounded free voice selection. No paid-provider fallback or automatic music."""
VOICES={'id':'id-ID-ArdiNeural','en':'en-US-GuyNeural'}
EDGE_VERSION='7.3.1'


def build(language='id',mode='tts'):
    if not isinstance(language,str) or not isinstance(mode,str) or language not in VOICES or mode not in ('tts','none'):
        raise ValueError('Suara harus tts/none, bahasa id/en')
    return {'provider':'edge','language':language,'mode':mode,'voice':VOICES[language],'rate':'+0%','music':False}


def validate(value):
    if not isinstance(value,dict) or set(value)-{'provider','language','mode','voice','rate','music'}:
        raise ValueError('Pengaturan suara tidak valid')
    result=build(value.get('language','id'),value.get('mode','tts'))
    if any(type(value[key]) is not type(result[key]) or value[key]!=result[key] for key in value):
        raise ValueError('Video Studio hanya mendukung suara Edge gratis yang dipilih, tanpa musik otomatis')
    return result
