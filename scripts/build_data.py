"""Deterministic, curated HWPX extraction. No model-generated action text."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
ET.register_namespace('hp', HP)
PROCESS = 'Ⅴ. 기관대응수칙 / 2. 산불재난 대응 프로세스'
GUIDE = 'Ⅲ. 위기관리 기본방향 / 3. 위기대응 지침 및 판단·고려 요소'
RESPONSE = 'Ⅳ. 위기경보 수준별 조치사항 / 1. 비상단계별 조치사항 / 다. 대응 단계'
RECOVERY = 'Ⅳ. 위기경보 수준별 조치사항 / 1. 비상단계별 조치사항 / 라. 복구 단계'

# WF IDs and short titles are application navigation labels, not official manual codes.
# Each tuple: short label, section member number, zero-based XML preorder index, heading.
SPECS = [
 ('위기징후 감시·평가', ['징후 감지'], ['산불방지과'], [
  ('감시수단 분석', 5, 885, PROCESS), ('위기징후 평가·정보 공유', 5, 923, PROCESS),
  ('담당자 정위치', 5, 939, PROCESS)]),
 ('상황접수·피해 파악', ['징후 감지'], ['중앙산불상황실'], [
  ('산불 신고 접수', 5, 308, PROCESS), ('산불발생 상황 파악', 5, 346, PROCESS),
  ('피해현황 파악', 5, 355, PROCESS), ('피해 확대 가능성 판단', 5, 367, PROCESS)]),
 ('상황 전파·보고', ['징후 감지', '초기 대응'], ['중앙산불상황실'], [
  ('청·차장 유선보고', 5, 423, PROCESS), ('유관기관 전파', 5, 432, PROCESS),
  ('필수요원 비상소집', 5, 439, PROCESS), ('상황보고서 작성·전파', 5, 534, PROCESS)]),
 ('초기 진화자원 투입', ['징후 감지', '초기 대응'], ['중앙산불상황실', '산림청', '지자체', '소방청'], [
  ('진화자원 즉시 출동', 3, 1161, GUIDE), ('헬기·지상자원 투입', 5, 380, PROCESS),
  ('지상·공중 진화활동', 5, 541, PROCESS)]),
 ('상황판단회의·대응단계 검토', ['초기 대응'], ['중앙산불상황실', '청·차장'], [
  ('대응단계·동원령 검토', 5, 673, PROCESS), ('상황판단회의 준비', 5, 679, PROCESS),
  ('현장상황·대처상황 점검', 5, 1321, PROCESS), ('회의 후속조치 이행', 5, 704, PROCESS)]),
 ('산불현장 통합지휘', ['초기 대응', '비상 대응'], ['산불현장 통합지휘본부'], [
  ('확산·확산 우려 시 본부 설치', 3, 1181, GUIDE), ('현장 대책회의·임무부여', 3, 1191, GUIDE),
  ('지상·공중 통신망 확보', 3, 1238, GUIDE), ('우선순위에 따른 진화', 3, 1264, GUIDE)]),
 ('위험구역 설정·주민대피', ['징후 감지', '초기 대응', '비상 대응'], ['중앙산불상황실', '산림청', '지자체'], [
  ('확산예측·위험구역 설정', 5, 360, PROCESS), ('산불발생 시 재난문자', 5, 374, PROCESS),
  ('대피권고 시 재난문자', 5, 501, PROCESS), ('대피명령 시 재난문자', 6, 129, PROCESS),
  ('안전취약계층 우선 대피', 6, 146, PROCESS), ('기관별 대피 역할', 3, 1340, GUIDE)]),
 ('중앙사고수습본부 운영', ['초기 대응', '비상 대응'], ['청·차장', '중앙사고수습본부', '산불방지과'], [
  ('추가피해 가능성에 따른 가동', 5, 1364, PROCESS), ('필요시 중수본 운영', 6, 278, PROCESS),
  ('중대본과 연락', 6, 480, PROCESS), ('대책회의 주재', 6, 487, PROCESS)]),
 ('관계기관 지원·자원 동원', ['초기 대응', '비상 대응'], ['청·차장', '산림재난통제관'], [
  ('관계기관 대책회의 필요시', 5, 1391, PROCESS), ('관계부처 협업사항', 5, 1407, PROCESS),
  ('현장상황에 따른 추가자원', 5, 1412, PROCESS), ('범정부 지원 요청 필요시', 6, 499, PROCESS),
  ('이재민 수용시설·구호품', 6, 504, PROCESS)]),
 ('언론 브리핑·오보 대응', ['초기 대응', '비상 대응', '수습·복구'], ['대변인'], [
  ('필요시 보도자료·브리핑', 5, 1852, PROCESS), ('현장대변인 핫라인', 5, 1859, PROCESS),
  ('언론 모니터링·오보 대응', 6, 919, PROCESS), ('중대본과 사전 협의', 6, 926, PROCESS),
  ('수습상황 브리핑', 6, 982, PROCESS)]),
 ('잔불진화·뒷불감시', ['비상 대응'], ['산림청', '지자체'], [
  ('잔불 진화', 3, 1302, GUIDE), ('뒷불감시 인력 배치', 3, 1302, GUIDE), ('감시조·책임담당제', 3, 14008, RESPONSE),
  ('발생·진화·피해 보고', 3, 14024, RESPONSE)]),
 ('피해조사·수습·복구', ['수습·복구'], ['산림청', '지방자치단체', '소관부서'], [
  ('산불전문조사반 운영', 3, 14440, RECOVERY), ('원인·확산경로 조사', 3, 14451, RECOVERY),
  ('피해 유형별 복구대책', 3, 14480, RECOVERY), ('응급복구·항구복구', 3, 14496, RECOVERY),
  ('피해지역 생활안정 지원', 6, 664, PROCESS)])
]


def paragraph_text(element):
    """Keep text after HWP inline controls; plain .text silently loses critical clauses."""
    def inline(t):
        result = t.text or ''
        for child in t:
            if child.tag.rsplit('}', 1)[-1] in ('lineBreak', 'tab', 'fwSpace', 'nbSpace'):
                result += ' '
            else:
                result += inline(child)
            result += child.tail or ''
        return result
    return re.sub(r'\s+', ' ', ''.join(inline(t) for t in element.iter(f'{{{HP}}}t'))).strip()


def build(path):
    raw = path.read_bytes()
    source = {'id': 'KFS-2026-06', 'title': '「산불 재난」 위기대응 실무매뉴얼',
              'publisher': '산림청', 'edition': '2026. 6.', 'filename': path.name,
              'sha256': hashlib.sha256(raw).hexdigest(),
              'locatorNote': 'HWPX 내부 XML 위치입니다. 인쇄 쪽수는 추정하지 않았습니다.',
              'extractionNote': '원문 문단의 문자·기호를 보존하며 줄바꿈과 공백만 정규화합니다.'}
    excerpts = ET.Element('excerpts', {'sourceSha256': source['sha256']})
    evidence, workflows = {}, []
    with ZipFile(path) as archive:
        roots = {n: ET.fromstring(archive.read(f'Contents/section{n}.xml')) for n in [3, 5, 6]}
        for index, (title, phases, agencies, actions) in enumerate(SPECS, 1):
            wid = f'WF-{index:03}'
            nodes = []
            for j, (label, section, position, heading) in enumerate(actions, 1):
                element = list(roots[section].iter())[position]
                assert element.tag == f'{{{HP}}}p', (section, position)
                eid = f'S{section}-E{position}'
                quote = paragraph_text(element)
                assert quote, eid
                if eid not in evidence:
                    evidence[eid] = {'id': eid, 'sourceId': source['id'], 'heading': heading,
                        'member': f'Contents/section{section}.xml', 'elementIndex': position,
                        'paragraphId': element.get('id'), 'quote': quote,
                        'sha256': hashlib.sha256(quote.encode()).hexdigest()}
                    wrapper = ET.SubElement(excerpts, 'excerpt', {'id': eid})
                    wrapper.append(element)
                nodes.append({'id': f'{wid}-N{j:02}', 'label': label, 'text': quote,
                              'evidenceIds': [eid], 'kind': 'action'})
            workflows.append({'id': wid, 'title': title, 'phases': phases, 'agencies': agencies,
                'evidenceIds': [n['evidenceIds'][0] for n in nodes], 'nodes': nodes,
                'edges': [{'source': wid, 'target': n['id'], 'kind': 'contains',
                           'label': '수록 조치', 'evidenceIds': n['evidenceIds']} for n in nodes]})
    workflows[10]['edges'].append({'source': 'WF-011-N01', 'target': 'WF-011-N02',
        'kind': 'after', 'label': '잔불 진화 후', 'evidenceIds': ['S3-E1302']})
    workflows[7]['edges'].append({'source': 'WF-008-N01', 'target': 'WF-008-N02',
        'kind': 'conditional', 'label': '추가피해 가능성에 따라', 'evidenceIds': ['S5-E1364', 'S6-E278']})
    result = {'version': '0.1.0', 'source': source, 'phases': ['징후 감지', '초기 대응', '비상 대응', '수습·복구'],
       'editorialNote': 'WF 번호·업무명·검색 분류는 서비스용 매핑입니다. 매뉴얼의 공식 코드나 의무 실행 순서를 뜻하지 않습니다.',
       'graphNote': '실선은 업무에 포함된 조치입니다. 화살표가 없는 선은 선후 관계를 뜻하지 않습니다. 조건은 원문에서 확인하십시오.',
       'workflows': workflows, 'evidence': evidence}
    return result, ET.tostring(excerpts, encoding='unicode', xml_declaration=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manual', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    data, xml = build(args.manual)
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    target = ROOT / 'data'
    if args.check:
        assert (target / 'workflows.json').read_text() == serialized, 'JSON differs from original manual'
        assert (target / 'source-excerpts.xml').read_text() == xml, 'XML differs from original manual'
        print(f"Original HWPX verified: {len(data['evidence'])} excerpts, SHA256 {data['source']['sha256']}")
    else:
        target.mkdir(exist_ok=True)
        (target / 'workflows.json').write_text(serialized, encoding='utf-8')
        (target / 'source-excerpts.xml').write_text(xml, encoding='utf-8')
        print(f"Built {len(data['workflows'])} workflows / {len(data['evidence'])} source excerpts")
