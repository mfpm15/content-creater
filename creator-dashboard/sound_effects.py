"""Short original procedural effects only. Zero signal outside approved cue windows."""
import math
import wave


def write(path, duration, cues, sample_rate=48000):
    events=[]
    for cue in cues:
        name=cue['cue'].strip().lower()
        if name in ('none','silence','diam','tanpa suara','-'):continue
        kind='chime' if any(x in name for x in ('chime','bell','ding')) else 'whoosh' if any(x in name for x in ('whoosh','swish','sapu','geser')) else 'hit' if any(x in name for x in ('hit','thud','impact','ketuk','mechanical')) else 'click'
        length={'chime':.32,'whoosh':.28,'hit':.16,'click':.055}[kind]
        events.append((float(cue['at']),length,kind))
    events.sort()
    cursor=0;active=[]
    with wave.open(str(path),'wb') as output:
        output.setparams((1,2,sample_rate,0,'NONE','not compressed'))
        block=bytearray()
        for i in range(round(duration*sample_rate)):
            t=i/sample_rate;value=0.0
            while cursor<len(events) and events[cursor][0]<=t:
                active.append(events[cursor]);cursor+=1
            active=[event for event in active if t<event[0]+event[1]]
            # An absolute sample hash keeps repeat renders deterministic.
            h=((i+1)*0x9e3779b9)&0xffffffff;h^=h>>16;h=(h*0x7feb352d)&0xffffffff;h^=h>>15
            noise=h/2147483648-1
            for start,length,kind in active:
                local=t-start
                if not 0<=local<length:continue
                u=local/length
                if kind=='whoosh':signal=noise*.4+math.sin(2*math.pi*(170*local+900*local*local))*.3;envelope=math.sin(math.pi*u)**2
                elif kind=='chime':signal=math.sin(2*math.pi*880*local)*.55+math.sin(2*math.pi*1320*local)*.25;envelope=math.sin(min(1,u/.04)*math.pi/2)*math.exp(-5*u)
                elif kind=='hit':signal=math.sin(2*math.pi*100*local)*.6+noise*.3;envelope=math.sin(min(1,u/.03)*math.pi/2)*math.exp(-7*u)
                else:signal=noise*.5+math.sin(2*math.pi*900*local)*.3;envelope=math.sin(math.pi*u)*math.exp(-6*u)
                value+=signal*envelope*.22
            block.extend(round(max(-1,min(1,value))*32767).to_bytes(2,'little',signed=True))
            if len(block)>=sample_rate*2:output.writeframes(block);block.clear()
        output.writeframes(block)
