"""Source-preserving curated excerpts for Miryang typhoon/rain and snow SOPs."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
if __package__:
    from scripts.build_data import paragraph_text, HP
else:
    from build_data import paragraph_text, HP

ROOT = Path(__file__).resolve().parents[1]
PHASES = ['징후 감지', '초기 대응', '비상 대응', '수습·복구']
# IDs are navigation labels. Shared tasks are stored once and selected by applicability.
COMMON = [
 ('사전대비·기상감시', 0, ['안전재난과'], [105304,105310,105316,105372,105405]),
 ('대비 총괄·취약시설 예찰', 0, ['안전재난과','시설별 해당부서'], [107136,107144,107150,107187]),
 ('초기 대응·상황보고', 1, ['안전재난과'], [107282,107292,107298,107322,107328]),
 ('초기 응급복구·홍보', 1, ['시설별 해당부서','공보감사담당관'], [107365,107401,107407]),
 ('비상 상황관리·자원지원', 2, ['안전재난과'], [107462,107469,107672,107678]),
 ('이재민 구호·유족지원', 2, ['주민복지과'], [107504,107510]),
 ('긴급통신·통신시설 복구', 2, ['정보통신과'], [107545,107551,107557]),
 ('시설물·에너지 응급복구', 2, ['소관부서','지역경제과'], [107592,107627,107635]),
 ('교통대책·사회질서 유지', 2, ['교통행정과','밀양경찰서'], [107713,107719,107867,107873]),
 ('의료·방역·수색구조구급', 2, ['보건위생과','밀양소방서'], [107754,107760,107910,107916]),
 ('환경정비·자원봉사·홍보', 2, ['환경관리과','주민복지과','공보감사담당관'], [107795,107830,107952]),
]
# Retain phase and alert conditions from the manual's explicit hazard-specific tables.
SPECIFIC = [
 ('TR-001','태풍 징후감시·대비', 'typhoon-rain',0,'태풍정보',[105664,105675,105680,105687,105692,105708,105715]),
 ('TR-002','태풍 초기 대응', 'typhoon-rain',1,'태풍 예비특보',[105754,105761,105767,105774,105791,105798,105807,105818,105823,105828,105843]),
 ('TR-003','태풍 비상 대응·대피', 'typhoon-rain',2,'태풍주의보·경보',[105875,105882,105887,105895,105901,105908,105915,105927,105934,105957,105976,105989,105998]),
 ('TR-004','태풍 수습·복구', 'typhoon-rain',3,'특보 해제',[106030,106044,106058,106067]),
 ('TR-005','호우 징후감시·대비', 'typhoon-rain',0,'호우 예비특보',[106138,106149,106154,106161,106173,106189,106196]),
 ('TR-006','호우 초기 대응', 'typhoon-rain',1,'호우주의보 및 피해 시작',[106239,106246,106252,106257,106274,106281,106288,106299,106304,106309,106322]),
 ('TR-007','호우 비상 대응·대피', 'typhoon-rain',2,'호우경보 및 피해 확산',[106356,106363,106368,106374,106380,106385,106392,106404,106411,106432,106450,106462,106471]),
 ('TR-008','호우 수습·복구', 'typhoon-rain',3,'특보 해제',[106503,106517,106531,106540]),
 ('SN-001','대설 징후감시·제설 준비','snow',0,'대설 예비특보',[106610,106621,106626,106633,106645,106660,106667,106680,106687]),
 ('SN-002','대설 초기 대응·제설 가동','snow',1,'대설주의보·경보',[106717,106724,106730,106735,106750,106757,106764,106777,106782,106787,106800]),
 ('SN-003','대설 비상 대응·대피','snow',2,'대설경보 및 대규모 재난 위험',[106833,106840,106845,106851,106857,106862,106867,106879,106886,106905,106924,106937,106946]),
 ('SN-004','대설 수습·복구','snow',3,'특보 해제',[106978,106992,107006,107015]),
]

def build(path):
    source = {'id':'MIRYANG-WEATHER-2026-06', 'title':'「풍수해(태풍·호우, 대설) 재난」 현장조치 행동매뉴얼',
        'publisher':'경상남도 밀양시','edition':'2026. 6.','filename':path.name,
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'locatorNote':'HWPX 내부 XML 위치이며 인쇄 쪽수는 추정하지 않았습니다.',
        'extractionNote':'주요 대응업무 발췌입니다. 원문 문자·기호를 보존하고 공백만 정규화합니다. 전체 매뉴얼을 대체하지 않습니다.'}
    with ZipFile(path) as z:
        elements=list(ET.fromstring(z.read('Contents/section3.xml')).iter())
    evidence={}; workflows=[]; excerpts=ET.Element('excerpts',{'sourceSha256':source['sha256']})
    specs=[(f'FW-{i:03}',title,'common',phase,'태풍·호우·대설 공통',positions,agencies)
           for i,(title,phase,agencies,positions) in enumerate(COMMON,1)]
    specs += [(*s,['밀양시 재난안전대책본부장']) for s in SPECIFIC]
    for wid,title,kind,phase,condition,positions,agencies in specs:
        nodes=[]
        for n,pos in enumerate(positions,1):
            e=elements[pos];assert e.tag==f'{{{HP}}}p'
            assert not any(x.tag==f'{{{HP}}}p' for x in list(e.iter())[1:])
            quote=paragraph_text(e); assert quote
            eid=f'MY-S3-E{pos}'
            if eid not in evidence:
                evidence[eid]={'id':eid,'sourceId':source['id'], 'heading':'Ⅴ. 즉시가동 준비사항 및 본부장 임무와 역할 / '+condition,
                    'member':'Contents/section3.xml','elementIndex':pos,'paragraphId':e.get('id'),
                    'quote':quote,'sha256':hashlib.sha256(quote.encode()).hexdigest()}
                ET.SubElement(excerpts,'excerpt',{'id':eid}).append(e)
            label=quote.lstrip('•–‧○- ').strip()
            nodes.append({'id':f'{wid}-N{n:02}','label':label[:30]+('…' if len(label)>30 else ''),
                'text':quote,'evidenceIds':[eid],'kind':'action'})
        w={'id':wid,'title':title,'phases':[PHASES[phase]],'agencies':agencies,'condition':condition,
           'applicability':['typhoon-rain','snow'] if kind=='common' else [kind],
           'scope':'common' if kind=='common' else 'specific','nodes':nodes,
           'evidenceIds':[n['evidenceIds'][0] for n in nodes],
           'edges':[{'source':wid,'target':n['id'],'kind':'contains','label':'수록 조치','evidenceIds':n['evidenceIds']} for n in nodes]}
        if wid=='SN-003':
            w['reviewNote']='[확인 필요] 대설 원문에 “행정시장”으로 표기되어 있습니다. 원문을 보존했으며 밀양시 적용 직위는 담당부서 확인이 필요합니다.'
        workflows.append(w)
    return {'version':'0.2.0','source':source,'phases':PHASES,
       'editorialNote':'FW는 풍수해 공통, TR은 태풍·호우, SN은 대설 탐색용 코드입니다. 업무 제목·검색 분류는 편집 매핑이며 공식 코드나 실행 순서가 아닙니다.',
       'graphNote':'선은 업무 포함 관계이며 선후 관계를 의미하지 않습니다. 적용 조건과 원문을 확인하세요.',
       'workflows':workflows,'evidence':evidence}, ET.tostring(excerpts,encoding='unicode',xml_declaration=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manual',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
    data,xml=build(a.manual)
    for name,text in [('workflows.json',json.dumps(data,ensure_ascii=False,indent=2)+'\n'),('source-excerpts.xml',xml)]:
        target=ROOT/'data/weather'/name
        if a.check:assert target.read_text(encoding='utf-8')==text,name
        else:target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text,encoding='utf-8')
    print(f"Weather: {len(data['workflows'])} workflows, {len(data['evidence'])} exact excerpts; check={a.check}")
