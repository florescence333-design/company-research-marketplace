function indexSections(version) {
  return new Map((version?.reportItems || []).flatMap(section => [section, ...(section.subsections || [])])
    .map(section => [section.section_id, section]));
}

function summary(section) {
  if (!section) return { status: '없음', webSources: 0, length: 0 };
  return {
    status: ({ complete: '작성 완료', partial: '부분 작성', unavailable: '자료 확인 대기' })[section.status] || '자료 확인 대기',
    webSources: (section.source_ids || []).filter(id => id.startsWith('web-')).length,
    length: (section.body || '').length,
  };
}

export function compareReports(versions = {}) {
  const claude = indexSections(versions.claude);
  const gpt = indexSections(versions.gpt);
  return [...new Set([...claude.keys(), ...gpt.keys()])].map(id => {
    const left = summary(claude.get(id));
    const right = summary(gpt.get(id));
    const difference = left.status !== right.status ? '작성 상태 차이'
      : left.webSources !== right.webSources ? '웹 근거 수 차이'
      : left.length !== right.length ? '서술 분량 차이' : '표면상 동일';
    return { id, title: gpt.get(id)?.title || claude.get(id)?.title || id, claude: left, gpt: right, difference };
  });
}
