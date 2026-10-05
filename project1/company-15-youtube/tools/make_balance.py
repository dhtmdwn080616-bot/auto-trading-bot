#!/usr/bin/env python3
"""밸런스 게임 쇼츠 생성기. 사용: python3 make_balance.py OUTDIR
Chromium(headless)으로 장면 PNG를 만들고, numpy로 원본 음악·효과음을 합성해 ffmpeg로 mp4를 만든다.
외부 소재·저작물을 쓰지 않는다. 득표율 등 가짜 수치를 넣지 않는다."""
import sys, os, glob, subprocess, wave, shutil
import numpy as np
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
CHROME = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))[0]
SR = 44100

# (번호, A이모지, A문구, B이모지, B문구, A색(위,아래), B색(위,아래), 후크, 음정 이동, bpm)
V = [
 (1,"🍗","평생<br>치킨만 먹기","🍜","평생<br>라면만 먹기",("#b91c1c","#ef4444"),("#1d4ed8","#3b82f6"),"인생을 건<br>선택입니다",0,124),
 (2,"💰","월급 500만원<br>매일 야근","🕔","월급 300만원<br>매일 칼퇴",("#b45309","#f59e0b"),("#0f766e","#14b8a6"),"당신의<br>선택은?",2,118),
 (3,"☀️","평생<br>여름만 살기","❄️","평생<br>겨울만 살기",("#c2410c","#fb923c"),("#1e40af","#60a5fa"),"이건 진짜<br>어려워요",-2,128),
 (4,"🦸","투명인간이<br>되기","🕊️","하늘을<br>날아다니기",("#6d28d9","#a78bfa"),("#0369a1","#38bdf8"),"딱 하나만<br>가질 수 있다면?",4,122),
 (5,"📶","평생 와이파이<br>엄청 느림","🔋","평생 배터리<br>항상 20%",("#be123c","#fb7185"),("#4d7c0f","#a3e635"),"폰 쓰는 사람<br>주목",0,126),
 (6,"👀","읽씹<br>당하기","🙈","안읽씹<br>당하기",("#a21caf","#e879f9"),("#334155","#94a3b8"),"솔직히<br>이게 더 아파요",-3,120),
 (7,"🎮","핑 300<br>최고 사양","🖥️","프레임 20<br>핑 0",("#b91c1c","#f87171"),("#1d4ed8","#60a5fa"),"게이머라면<br>골라보세요",3,130),
 (8,"👥","친구<br>100명","🤝","평생 베프<br>딱 1명",("#047857","#34d399"),("#7c2d12","#fb923c"),"인간관계<br>밸런스",-1,116),
 (9,"📵","폰 없이<br>1년 살면 10억","📱","그냥 지금처럼<br>폰 쓰고 살기",("#0f172a","#475569"),("#be185d","#f472b6"),"10억이<br>걸렸습니다",1,122),
 (10,"⏪","과거로<br>돌아가기","⏩","미래로<br>가보기",("#7e22ce","#c084fc"),("#0e7490","#22d3ee"),"타임머신이<br>생겼어요",-4,124),
]

TPL = """<!doctype html><html lang="ko"><meta charset="utf-8"><style>
html,body{margin:0;width:1080px;height:2010px;overflow:hidden;font-family:"WenQuanYi Zen Hei","Noto Sans CJK KR","Noto Color Emoji",sans-serif;color:#fff;text-align:center}
.top,.bot{position:absolute;left:0;width:1080px;height:960px;display:flex;flex-direction:column;align-items:center;padding:0 60px;box-sizing:border-box}.top{justify-content:center;padding-bottom:150px}.bot{justify-content:flex-start;padding-top:170px}
.top{top:0;background:linear-gradient(180deg,%(a0)s,%(a1)s)}.bot{top:960px;background:linear-gradient(180deg,%(b0)s,%(b1)s)}
.e{font-size:170px;line-height:1}.t{font-size:88px;font-weight:800;line-height:1.3;margin-top:14px;text-shadow:0 6px 0 #0004}
.vs{position:absolute;top:960px;left:540px;transform:translate(-50%%,-50%%);width:260px;height:260px;border-radius:50%%;background:#fff;color:#111;font-size:120px;font-weight:900;display:flex;align-items:center;justify-content:center;box-shadow:0 10px 0 #0003;z-index:5}
.hook{position:absolute;inset:0;background:#111;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:0 80px;box-sizing:border-box;z-index:9}
.hook .big{font-size:150px;font-weight:900;line-height:1.3}.y{color:#ffe14a}
.cd{position:absolute;inset:0;background:#000b;z-index:8;display:flex;flex-direction:column;align-items:center;justify-content:center}
.cd .n{font-size:560px;font-weight:900;color:#ffe14a}.cd .s{font-size:80px}
.cta{position:absolute;bottom:230px;left:0;width:1080px;z-index:7;font-size:64px;text-shadow:0 4px 0 #0007}
</style><body>%(body)s</body></html>"""

def scenes(v):
    n,ae,at,be,bt,ac,bc,hook,_,_ = v
    base=(f'<div class="top"><div class="e">{ae}</div><div class="t">{at}</div></div>'
          f'<div class="bot"><div class="e">{be}</div><div class="t">{bt}</div></div><div class="vs">VS</div>')
    cd=lambda k:base+f'<div class="cd"><div class="n">{k}</div><div class="s">고민 중…</div></div>'
    return {
     "01":f'<div class="hook"><div class="big">{hook.replace("<br>","<br><span class=y>",1)}</span></div></div>' if False else f'<div class="hook"><div class="big">{hook}</div></div>',
     "02":base+'<div class="cta">딱 하나만 고를 수 있어요</div>',
     "03":base+f'<div class="cta">댓글로 {ae} or {be} ?</div>',
     "04":cd(3),"05":cd(2),"06":cd(1),
     "07":base+'<div class="cta">⏰ 시간 끝! 선택하셨나요?</div>',
     "08":f'<div class="hook"><div class="big">댓글에<br><span class="y">{ae} / {be}</span><br>남겨주세요</div></div>',
    }

DUR=[("01",2),("02",4),("03",2),("04",1),("05",1),("06",1),("07",2),("08",3)]

def synth(path, shift, bpm):
    N=int(SR*16.0); mix=np.zeros(N); rng=np.random.default_rng(7)
    def add(t0,s,g=1.0):
        i=int(t0*SR); j=min(N,i+len(s))
        if i<N: mix[i:j]+=s[:j-i]*g
    def tone(f,L,kind="sq",d=6):
        t=np.arange(int(L*SR))/SR
        s=np.sign(np.sin(2*np.pi*f*t)) if kind=="sq" else (2*np.abs(2*((f*t)%1)-1)-1 if kind=="tri" else np.sin(2*np.pi*f*t))
        e=np.minimum(1,t/0.004)*np.exp(-t*d); return s*e
    def kick():
        t=np.arange(int(.25*SR))/SR; f=120*np.exp(-t*25)+45
        return np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*14)
    def hat():
        t=np.arange(int(.05*SR))/SR; return rng.standard_normal(len(t))*np.exp(-t*90)
    def snare():
        t=np.arange(int(.18*SR))/SR; return (rng.standard_normal(len(t))*.8+np.sin(2*np.pi*190*t)*.4)*np.exp(-t*22)
    def whoosh():
        L=int(.35*SR); x=rng.standard_normal(L); e=np.sin(np.linspace(0,np.pi,L))**2
        return np.convolve(x,np.ones(30)/30,"same")*e
    k=2**(shift/12); beat=60/bpm; bar=beat*4
    def bar_music(t0):
        notes=[220,262,330,262,196,247,294,247]
        for i in range(8): add(t0+i*beat/2,tone(notes[i]*2*k,beat/2*.9,"sq",7),.07)
        for b in range(4):
            add(t0+b*beat,kick(),.55); add(t0+b*beat+beat/2,hat(),.18)
            if b%2==1: add(t0+b*beat,snare(),.22)
            add(t0+b*beat,tone([110,110,98,98][b]*k,beat*.9,"tri",3),.28)
    t=0.0
    while t<8.0-1e-6: bar_music(t); t+=bar
    t=11.0
    while t<16.0-bar+1e-6: bar_music(t); t+=bar
    add(0,kick(),.9); add(0,tone(60,.5,"sin",5),.5)
    for tt in (2.0,6.0): add(tt-.1,whoosh(),.35)
    add(2.0,kick(),.9); add(2.0,tone(80,.4,"sin",6),.5)
    for tt in (8.0,9.0,10.0): add(tt,tone(1000,.12,"sin",20),.6); add(tt,tone(2000,.06,"sin",30),.25)
    add(11.0,tone(180,.45,"sq",4),.35); add(11.0,tone(120,.45,"sq",4),.3)
    for f,g in ((880,.45),(1320,.3),(1760,.15)): add(13.0,tone(f,.9,"sin",4),g)
    m=int(1.2*SR); fade=np.ones(N); fade[-m:]=np.linspace(1,0,m); mix*=fade
    mix/=max(1e-9,np.max(np.abs(mix)))*1.15
    with wave.open(path,"wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix*32767).astype(np.int16).tobytes())

os.makedirs(OUT,exist_ok=True)
for v in V:
    n=v[0]; tmp=os.path.join(OUT,f"_tmp{n:02d}"); os.makedirs(tmp,exist_ok=True)
    ctx=dict(a0=v[5][0],a1=v[5][1],b0=v[6][0],b1=v[6][1])
    for k,body in scenes(v).items():
        h=os.path.join(tmp,f"s{k}.html"); open(h,"w",encoding="utf8").write(TPL%dict(ctx,body=body))
        raw=os.path.join(tmp,f"raw{k}.png")
        subprocess.run([CHROME,"--headless","--no-sandbox","--disable-gpu","--hide-scrollbars","--window-size=1080,2100",f"--screenshot={raw}",f"file://{h}"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        Image.open(raw).crop((0,0,1080,1920)).save(os.path.join(tmp,f"s{k}.png"))
    lst=os.path.join(tmp,"list.txt")
    with open(lst,"w") as f:
        for k,d in DUR: f.write(f"file 's{k}.png'\nduration {d}\n")
        f.write("file 's08.png'\n")
    synth(os.path.join(tmp,"bed.wav"),v[8],v[9])
    out=os.path.join(OUT,f"balance-{n:02d}.mp4")
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",lst,"-i",os.path.join(tmp,"bed.wav"),
        "-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","medium","-crf","20","-c:a","aac","-b:a","128k","-shortest","-movflags","+faststart",out],check=True)
    shutil.rmtree(tmp); print("made",out,flush=True)
