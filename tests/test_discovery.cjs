const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({document: {addEventListener() {}}, state: {}});
vm.runInContext(fs.readFileSync('web/app-discovery.js', 'utf8'), context);
const run = (code) => vm.runInContext(code, context);

test('multiple choices are OR within and across facets', () => {
  context.candidates = ['방어 +10 (해당 인물)', '방어 +10 (아군 수행원)', '방어 +10 (세력 전체)', '사기 +3 (아군 수행원)'];
  assert.equal(run(`candidates.filter(text => effectMatches(text, {target:['self']})).length`), 1);
  assert.equal(run(`candidates.filter(text => effectMatches(text, {target:['self','retinue']})).length`), 3);
  assert.equal(run(`candidates.filter(text => effectMatches(text, {target:['self','retinue'],purpose:['survival']})).length`), 4);
  assert.equal(run(`candidates.filter(text => effectMatches(text, {target:[]})).length`), 4);
  assert.equal(run(`effectMatches('결의 +5 (해당 인물) · 방어 +10 (세력 전체)', {target:['self','retinue'], purpose:['survival']})`), true);
  assert.equal(run(`effectMatches('방어 +10', {target:['self','unknown']})`), true);
});

test('title role and scope conditions are alternatives, including no-role effects', () => {
  context.title = '결의 +20 (해당 인물) · 사기 +3 (세력 지도자일 경우, 세력 전체) · 충원 +5% (통솔할 때) · 방어 +10 (아군 수행원)';
  assert.equal(run(`effectMatches(title, {role:'leader', target:'faction'})`), true);
  assert.equal(run(`effectMatches(title, {role:'leader', target:'self'})`), true);
  assert.equal(run(`effectMatches(title, {role:'commanding', purpose:'healing'})`), true);
  assert.equal(run(`effectMatches(title, {role:'unknown', target:'self'})`), true);
  assert.equal(run(`effectMatches(title, {role:'unknown', target:'faction'})`), true);
  assert.equal(run(`effectMatches(title, {target:'retinue', purpose:'survival'})`), true);
  assert.equal(run(`effectMatches('식량 +5 (태수가 있는 군)', {role:'governor', target:'province'})`), true);
  assert.equal(run(`effectMatches('수행원 유지비 -15% (세력 지도자일 경우, 세력 전체)', {target:'retinue'})`), false);
  assert.equal(run(`effectMatches('수행원 유지비 -20% (해당 인물)', {target:'retinue'})`), false);
  assert.equal(run(`effectMatches('수행원 유지비 -20% (해당 인물)', {target:'self'})`), true);
  assert.equal(run(`effectMatches('방어하는 적의 사기 -2 (해당 인물)', {target:'enemy'})`), false);
});

test('multiword search ignores order, whitespace and Latin case but requires every term', () => {
  assert.equal(run(`discoveryMatches('아군 근접 방어 +15% MTU', '방어 아군 mtu')`), true);
  assert.equal(run(`discoveryMatches('공공 질서 +5', '공공질서')`), true);
  assert.equal(run(`discoveryMatches('근접 방어 +15%', '방어 회복')`), false);
  assert.equal(run(`discoveryMatches('관우', '')`), true);
  assert.equal(run(`discoveryMatches('근접 방어 +15% (해당 인물)', '방어 본인')`), true);
});

test('scope and effect can match separate effect clauses', () => {
  const text = '결의 +20 (해당 인물) · 근접 방어 +15% (아군 수행원)';
  context.description = text;
  assert.equal(run(`effectMatches(description, {purpose:'survival', target:'self'})`), true);
  assert.equal(run(`effectMatches(description, {purpose:'survival', target:'retinue'})`), true);
  assert.equal(run(`effectMatches(description, {purpose:'stats', target:'self'})`), true);
});

test('missing scope and activation never imply self or passive', () => {
  assert.equal(run(`effectMatches('근접 방어 +15%', {target:'self'})`), false);
  assert.equal(run(`effectMatches('근접 방어 +15%', {activation:'passive'})`), false);
  assert.equal(run(`effectMatches('근접 방어 +15%', {target:'unknown', activation:'unknown'})`), true);
  assert.equal(run(`effectMatches('', {purpose:'unknown'})`), true);
});

test('active ability description retains target and numeric details within one clause', () => {
  assert.equal(run(`effectMatches('결의 +5 (해당 인물) · 능력: 철벽 — 발동 능력 · 자신 · 근접 방어 +50% · 재사용 대기시간 120초 (해당 인물)', {purpose:'survival', target:'self', activation:'active'})`), true);
  assert.equal(run(`effectMatches('능력: 가르기 — 갑옷 ×0.75 · 재사용 대기시간 120초 (해당 인물)', {purpose:'survival', target:'self'})`), true);
  assert.equal(run(`effectMatches('체력 비용 10% (해당 인물)', {purpose:'survival'})`), false);
  assert.equal(run(`effectMatches('방어하는 적의 사기 -2 (해당 인물)', {purpose:'survival'})`), false);
  assert.equal(run(`effectMatches('갑옷 관통 피해 +10% (해당 인물)', {purpose:'survival'})`), false);
});

test('opening a lazy picker retains its current value even when the catalog uses a different key', () => {
  const editor = fs.readFileSync('web/app-editor.js', 'utf8');
  const start = editor.indexOf('function ensureSelectOptionsLoaded');
  const end = editor.indexOf('\nfunction wireLazySelect', start);
  const lazy = vm.createContext({renderSelectOptions:(select, options, value)=>{select.value = options.some(o=>o.value===value) ? value : options[0].value;}});
  vm.runInContext(editor.slice(start,end),lazy);
  assert.equal(vm.runInContext(`
    const select = {value:'current',_allOptions:[{value:'current',label:'현재 칭호'}],_optionsLoaded:false,_optionLoader:()=>[{value:'catalog',label:'다른 칭호'}]};
    ensureSelectOptionsLoaded(select);
    select.value;
  `,lazy),'current');
});

test('skill search is isolated by editor, defaults to all results, and retains state', () => {
  run(`skillDiscoveryState('edit').query = '회복'; skillDiscoveryState('edit').filters.purpose = 'healing'`);
  assert.equal(run(`skillDiscoveryState('source').query`), '');
  assert.equal(run(`skillDiscoveryState('edit').query`), '회복');
  assert.equal(run(`Object.keys(skillDiscoveryState('source').filters).length`), 0);
});

test('favorite and element filters intersect without replacing gender', () => {
  const rosterContext = vm.createContext({state:{filter:'wood', favoritesOnly:true, workflowGender:'female'},
    matchesGender:(c,g)=>c.gender===g, isFavoriteCharacter:c=>c.favorite,
    ELEMENTS:{wood:{}, fire:{}}});
  const source = fs.readFileSync('web/app-catalog.js','utf8');
  vm.runInContext(source.slice(source.indexOf('function matchesRosterFilter'), source.indexOf('function characterFavoriteKey')), rosterContext);
  assert.equal(vm.runInContext(`matchesRosterFilter({element:'wood',gender:'female',favorite:true})`,rosterContext),true);
  assert.equal(vm.runInContext(`matchesRosterFilter({element:'wood',gender:'female',favorite:false})`,rosterContext),false);
  assert.equal(vm.runInContext(`matchesRosterFilter({element:'fire',gender:'female',favorite:true})`,rosterContext),false);
  assert.equal(vm.runInContext(`matchesRosterFilter({element:'wood',gender:'male',favorite:true})`,rosterContext),false);
});

 test('title stat joins facet filters by OR without an empty facet matching everything', () => {
  context.resolveTitleChoice = value => ({titleEffectSummary: value, stat: value.includes('본능')});
  context.titleChoiceMatchesStatFilter = title => title.stat;
  assert.equal(run(`discoveryChoiceMatches({id:'sourceTitle'}, {value:'본능 +10 (해당 인물)'}, {role:['commanding']}, 'instinct')`), true);
  assert.equal(run(`discoveryChoiceMatches({id:'editTitle'}, {value:'충원 +5 (통솔할 때)'}, {role:['commanding']}, 'instinct')`), true);
  assert.equal(run(`discoveryChoiceMatches({id:'editTitle'}, {value:'결의 +5 (해당 인물)'}, {role:['commanding']}, 'instinct')`), false);
  assert.equal(run(`discoveryChoiceMatches({id:'sourceTitle'}, {value:'결의 +5 (해당 인물)'}, {}, 'instinct')`), false);
  assert.equal(run(`discoveryChoiceMatches({id:'sourceTitle'}, {value:'결의 +5 (해당 인물)'}, {}, 'all')`), true);
  assert.equal(run(`effectMatches('사기 +5 (세력 전체)', {role:['commanding'], target:[], purpose:[]})`), false);
});

test('rendered title results use the union and retain independent text search', () => {
  context.escapeHtml = value => String(value);
  context.titleFilterForPrefix = () => 'instinct';
  const nodes = Object.fromEntries(['.discovery-status','.discovery-current','.discovery-results','[data-discovery-more]'].map(key => [key, {}]));
  const input = {value:''};
  context.select = {id:'sourceTitle', value:'결의 +5 (해당 인물)', selectedOptions:[],
    _allOptions:['본능 +10 (해당 인물)', '충원 +5 (통솔할 때)', '결의 +5 (해당 인물)'].map(value => ({value,label:value})),
    _effectFilters:{role:['commanding']},
    _discoveryPanel:{hidden:false,querySelector:key=>nodes[key]},parentNode:{querySelector:()=>input}};
  run('renderDiscoverySelect(select)');
  assert.match(nodes['.discovery-status'].textContent, /또는 본능 · 2개 결과/);
  assert.match(nodes['.discovery-results'].innerHTML, /본능/);
  assert.match(nodes['.discovery-results'].innerHTML, /충원/);
  assert.doesNotMatch(nodes['.discovery-results'].innerHTML, /결의/);
  assert.equal(context.select.value, '결의 +5 (해당 인물)');
  input.value='충원';
  run('renderDiscoverySelect(select)');
  assert.match(nodes['.discovery-status'].textContent, /1개 결과/);
  assert.doesNotMatch(nodes['.discovery-results'].innerHTML, /본능/);
  assert.equal(run(`effectMatches('능력: 가르기 — 갑옷 ×0.75 · 재사용 대기시간 120초 (해당 인물)', {target:'self'})`), false);
});
