'use strict';
const SOURCE_PROFILE_LABELS = {
  'vanilla-mtu-v1': '바닐라·MTU',
  '190': '바닐라·MTU·190 Expanded',
  '190-korea': '바닐라·MTU·190 Expanded·한반도',
};
state.sourceProfile = 'vanilla-mtu-v1';

function requestedSourceProfile() {
  return $('includeKoreaData').checked ? '190-korea' : $('include190Data').checked ? '190' : 'vanilla-mtu-v1';
}

function queueProfileBlocked(item) {
  return (item.sourceProfile || 'vanilla-mtu-v1') !== state.sourceProfile;
}

function renderSourceProfile() {
  const pending = requestedSourceProfile() !== state.sourceProfile;
  const blocked = state.queue.filter(queueProfileBlocked).length;
  $('sourceProfileStatus').textContent = `적용 중: ${SOURCE_PROFILE_LABELS[state.sourceProfile]}${pending ? ' · 변경 사항은 적용 버튼을 눌러주세요.' : ''}${blocked ? ` · 이전 구성 작업 ${blocked}개 보류 (작업은 유지됩니다).` : ''}`;
}

$('include190Data').addEventListener('change', () => {
  if (!$('include190Data').checked) $('includeKoreaData').checked = false;
  renderSourceProfile();
});
$('includeKoreaData').addEventListener('change', () => {
  if ($('includeKoreaData').checked) $('include190Data').checked = true;
  renderSourceProfile();
});
$('applySourceProfile').addEventListener('click', async () => {
  if (state.loadingPack || buildInFlight) return;
  $('applySourceProfile').disabled = true;
  try { await loadPack({ sourceProfile: requestedSourceProfile() }); }
  finally { $('applySourceProfile').disabled = false; renderSourceProfile(); }
});
renderSourceProfile();
