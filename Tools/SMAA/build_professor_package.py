"""Portable local gallery and explicitly distinct full/compact attachment packages."""
import hashlib,html,json,re,zipfile
from pathlib import Path
from html.parser import HTMLParser

OUT=Path('C:/Users/USER/Desktop/research/Deliverables/TSCMAA_Professor_20261001')
MEDIA=OUT/'media'

def gallery(compact=False):
    short=json.loads((OUT/'short-media-manifest.json').read_text(encoding='utf-8'))['media']
    long=json.loads((OUT/'long-media-manifest.json').read_text(encoding='utf-8'))['media']
    assert len(short)==5 and len(long)==2
    def card(r):
        name=r['name'];title=html.escape(r['title']);secs=r['video']['duration_seconds']
        links=''
        if not compact:
            links=''.join(f'<a class="button" href="media/{r["gifs"][speed]["file"]}">{label} GIF · {r["gifs"][speed]["seconds"]:g}초</a>'
                          for speed,label in [('slow','느리게 1/6×'),('fast','빠르게 0.83×')])
        links+=f'<a class="button" href="media/{r["video"]["file"]}" download>MP4 저장</a>'
        sheets=''
        if r.get('sheets'):
            phases=[('moving','이동 f130–135'),('transition','전환 f178–183'),('still','정지 f190–195')]
            sheets='<details><summary>연속 원본 프레임 검사 PNG</summary><ul>'+''.join(
                f'<li>{title2}: <a href="media/{name}-{phase}-1to4-six.png">①–④</a> · <a href="media/{name}-{phase}-5to8-six.png">⑤–⑧</a></li>' for phase,title2 in phases)+'</ul></details>'
        note='화면 고정 ROI · 원본 색 · nearest 확대' if 'roi' in r else '새 경로 · 정지 1초 → 이동 6초 → 정지 1초 · 전체 화면 축소'
        return f'''<article id="{name}"><h3>{title}</h3><p>{note} · 정상 재생 {secs:g}초</p>
<video id="v-{name}" controls loop playsinline preload="none" poster="media/{r['poster']}" src="media/{r['video']['file']}"></video>
<div class="controls"><label>영상 재생 <select data-video="v-{name}"><option value="1">정상 속도 1×</option><option value="0.1666666667">느리게 1/6×</option><option value="2">빠르게 2×</option></select></label>{links}</div>{sheets}</article>'''
    content='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SMAA ①–⑧ 연구 비교 자료</title>
<style>:root{color-scheme:dark}*{box-sizing:border-box}body{font:16px/1.65 "Malgun Gothic",sans-serif;margin:0;background:#111518;color:#edf1f4}main{max-width:1640px;margin:auto;padding:28px}header{max-width:1150px}h1{font-size:30px;margin:12px 0}h2{margin-top:48px}h3{margin:0 0 8px}p{color:#bbc5cc}a{color:#83d9ec}nav{display:flex;gap:12px;flex-wrap:wrap;margin:25px 0}.button,button{display:inline-block;background:#23343d;border:1px solid #42515b;border-radius:6px;padding:8px 12px;color:#d8eff5;text-decoration:none}article{background:#1b2228;border:1px solid #37444e;border-radius:10px;margin:24px 0;padding:22px}video{display:block;max-width:100%;height:auto;margin:auto;background:#111518}select{font:inherit;background:#202c34;color:white;padding:8px;border:1px solid #526372;border-radius:6px}.controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:16px 0}details{margin-top:14px}summary{cursor:pointer}table{border-collapse:collapse;max-width:1100px;width:100%;font-size:14px}td,th{border:1px solid #42515b;padding:8px;text-align:left}strong{color:white}.notice{border-left:3px solid #70ccdf;padding-left:18px}footer{margin:40px 0;color:#a5b5bf}</style></head><body><main><header>
<p>전병훈 · 2026.10.01 · 교수님 보고 자료</p><h1>SMAA ①–⑧ 속도·품질 비교</h1>
<p>모든 비교의 위쪽은 ①·②·③·④, 아래쪽은 ⑤·⑥·⑦·⑧입니다. 기준선은 ④입니다.</p>
<nav><a class="button" href="메일_초안.html">설명·성능·품질 표 / 메일 초안</a><a class="button" href="#short">5개 확대 구간</a><a class="button" href="#long">새 8초 경로 2개</a></nav>
<table><tr><th>구성</th><th>공간 AA / Temporal 범위</th><th>표본 패턴</th></tr>
<tr><td>① AA-Off</td><td>없음 / 없음</td><td>Off</td></tr><tr><td>② SMAA 1X</td><td>원본 SMAA / 없음</td><td>Off</td></tr><tr><td>③ Temporal-only</td><td>없음 / 전체 화면</td><td>On</td></tr><tr><td>④ 원본 SMAA T2X-R</td><td>원본 SMAA / 전체 화면</td><td>On</td></tr><tr><td>⑤ Edge temporal-only</td><td>없음 / 현재 edge</td><td>Off</td></tr><tr><td>⑥ SMAA + 현재 edge</td><td>원본 SMAA / 현재 edge</td><td>Off</td></tr><tr><td>⑦ 직전 edge 유지 · 개선 전</td><td>원본 SMAA / 현재 + 재투영한 직전 raw edge</td><td>Off</td></tr><tr><td>⑧ 직전 edge 유지 · 개선 후</td><td>⑦과 같은 결과 / 실행 비용 개선</td><td>Off</td></tr></table>
<p class="notice"><strong>속도 개선과 품질 개선은 구분합니다.</strong> ⑦·⑧의 RGB는 같고, 얇은 선 단절은 남아 있습니다. ③·④와 선택적 처리의 표본 패턴이 달라 그 차이 전체를 edge 선택 효과로 해석할 수 없습니다. CGVQM-2는 보조 지표입니다.</p>
<p>MP4는 60fps 정상 속도입니다. 느린 GIF는 1/6배속, 빠른 GIF는 약 0.83배속이며 원본 프레임을 모두 유지했습니다. GIF는 고정 256색, MP4는 손실 압축이므로 정확한 픽셀 비교에는 무손실 PNG를 사용합니다. 화면 전체 축소 영상은 경로 확인용입니다.</p>
'''
    if compact:content+='<p><strong>이 파일은 소용량 영상 묶음입니다.</strong> GIF는 전체 자료 ZIP에 포함되며 여기서는 MP4 재생 속도를 바꿔 확인할 수 있습니다.</p>'
    content+='</header><h2 id="short">5개 확대 구간 · 원본 4초</h2>'+''.join(card(r) for r in short)
    content+='<h2 id="long">새 8초 경로 · 480프레임씩</h2><p>기존 4초 자료를 반복하지 않고 실제 이동 구간을 연장했습니다. 독립 3D 장면은 Bistro와 Minecraft 두 개입니다.</p>'+''.join(card(r) for r in long)
    content+='''<footer>압축을 해제한 뒤 index.html을 여세요. 영상과 표는 서버 연결 없이 열립니다. 별도 측정한 기존 성능·CGVQM 결과와 이번 추가 발표용 캡처를 구분했습니다.</footer></main>
<script>document.querySelectorAll('select[data-video]').forEach(s=>s.addEventListener('change',()=>document.getElementById(s.dataset.video).playbackRate=Number(s.value)));document.querySelectorAll('video').forEach(v=>v.addEventListener('play',()=>document.querySelectorAll('video').forEach(other=>{if(other!==v)other.pause()})));</script></body></html>'''
    return content

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in ('src','href','poster') and v and not v.startswith(('#','http:','https:')):self.links.append(v)

def main():
    for name,compact in [('index.html',False),('index-video.html',True)]:
        content=gallery(compact);parser=Links();parser.feed(content)
        for link in parser.links:assert (OUT/link).is_file(),link
        (OUT/name).write_text(content,encoding='utf-8')
    (OUT/'읽어주세요.txt').write_text('압축을 해제한 뒤 index.html을 여세요.\n위 ①②③④ / 아래 ⑤⑥⑦⑧. 기준선 ④.\n메일 초안과 5개 ROI + 새 8초 경로 2개를 포함합니다.\n느린 GIF 1/6배속 / 빠른 GIF 0.833배속 / MP4 60fps 정상 속도.\n원본 프레임을 생략하거나 보간하지 않았습니다.\nGIF는 256색, MP4는 손실 압축이므로 미세 비교에는 PNG를 사용합니다.\n',encoding='utf-8')
    files=sorted(p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='package-validation.json')
    manifest={str(p.relative_to(OUT)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
    packages=[]
    for compact,filename in [(False,'TSCMAA_전체자료.zip'),(True,'TSCMAA_메일첨부_영상중심.zip')]:
        selected=[p for p in files if not compact or (p.suffix!='.gif' and p.name not in ('index.html','long-media-manifest.json','measurement-provenance.json'))]
        target=OUT/filename
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for p in selected:
                arc=str(p.relative_to(OUT)).replace('\\','/')
                if compact and arc=='index-video.html':arc='index.html'
                archive.write(p,arcname=arc)
        with zipfile.ZipFile(target) as archive:
            assert archive.testzip() is None
            parser=Links();parser.feed(archive.read('index.html').decode('utf-8'))
            assert all(l in archive.namelist() for l in parser.links)
        packages.append(dict(file=filename,bytes=target.stat().st_size,zip_crc='PASS',links='PASS'))
        print('PASS ZIP',filename,round(target.stat().st_size/1e6,2),'MB',flush=True)
    (OUT/'package-validation.json').write_text(json.dumps(dict(packages=packages,files=manifest),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS portable links and ZIP CRC',flush=True)

if __name__=='__main__':main()
