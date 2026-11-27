const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function harness() {
  const nodes = new Map();
  const calls = [];
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {id, value:'', checked:false, dataset:{}, options:[],
      classList:{toggle(){}}, parentNode:{querySelector(){return null;}}, addEventListener(){}});
    return nodes.get(id);
  };
  const base = {key:'base',name:'Base',element:'fire',weight:1,minRound:0,maxRound:999,gender:'female'};
  const donor = {...base,key:'donor',name:'Donor'};
  const c = vm.createContext({console, state:{queue:[],workflowGender:'female',selectedKey:'base',skillTreeDrafts:{},formOptionsSignature:'keep'},
    document:{addEventListener(){},querySelectorAll(){return [];}}, $:node,
    characters:()=>[base,donor], selectedCharacter:()=>base, realTemplateKey:x=>x.key,
    characterGenderKey:x=>x.gender, syncWorkflowGender:g=>{c.state.workflowGender=g;},
    skillSetKeyForEditor:()=> 'skills', skillDraftKey:(p,k)=>`${p}:${k}`,
    SPAWN_EVENTS:[{key:'start',name:'Start',note:''},{key:'delayed_join',name:'Later',note:''}],
    ELEMENTS:{fire:{subtype:'fire',label:'Fire',name:'Fire'}}, elementMeta:()=>({subtype:'fire'}),
    createSubtypeOptions:()=>[{value:'fire',label:'Fire'}], option:(value,label,search='')=>({value,label,search}),
    CEO_SET_BASE_VALUE:'__base__', ATTRIBUTE_FIELDS:[['Resolve','resolve']],
    attributeChoiceValueFor:x=>x, birthYearForAgeRange:()=>null,
    generatedSpawnEventFromRound:x=>Number(x)>0?'delayed_join':'start', queueProfileBlocked:()=>false,
    appearanceByKey:key=>({key,name:'Saved image'}), appearanceOption:x=>({value:x.key,label:x.name}),
    resolveTitleChoice:key=>({key}), titleChoiceValue:x=>x.key,titleOptionLabel:()=> 'Saved title',titleSearchText:()=>'',
    resolveAttributeChoice:key=>({key}),attributeOptionLabel:()=> 'Saved attributes',
    ceoSetChoices:()=>[{key:'trait'},{key:'gear'},{key:'__base__'}],
    ceoSetOptionLabel:x=>x.key,ceoSetOptionSearch:()=>'',
    traitSetOption:x=>({value:x.key,label:'Saved trait'}),equipmentSetOption:x=>({value:x.key,label:'Saved gear'}),
    baseCharacterOptionLabel:x=>x.name, characterSearchText:()=>'',skillSourceOptionLabel:x=>x.name,
    equipmentBrief:()=>'',displayLabel:x=>x,
    enhanceSearchableSelect(){},renderDiscoverySelect(){},
  });
  vm.runInContext(fs.readFileSync('web/app-editor.js','utf8'),c);
  vm.runInContext(fs.readFileSync('web/app-queue.js','utf8'),c);
  c.enhanceSearchableSelect=()=>{};
  c.attributeOptionLabel=()=> 'Saved attributes';
  c.titleSearchText=()=>'';
  c.baseCharacterOptionLabel=x=>x.name;
  c.skillSourceOptionLabel=x=>x.name;
  c.attributeChoiceValueFor=x=>x;
  c.resolveAttributeChoice=key=>({key});
  c.renderSelectOptions=(select,options,selected)=>{
    select.options=options.map(x=>({value:String(x.value)}));
    select.value=select.options.some(x=>x.value===String(selected))?String(selected):(select.options[0]?.value||'');
  };
  for(const name of ['renderWorkflowGenderButtons','renderTitleFilterButtons','renderTitleSummary','syncCeoSetSummary',
    'syncModelLockSummaries','syncEquipmentSummary','syncAttributeSummary','syncUnitSummary','updateImagePreview',
    'updateSpawnFieldLabels','renderSkillTreeEditor','syncDedicatedArmourControls','renderRoster','updateRosterActiveState',
    'refreshStageButtons','renderSelectedPreview','renderValidation','setWorkView','clearReferenceEditWarning']) {
    c[name]=(...args)=>calls.push([name,...args]);
  }
  for(const name of ['fillForms','renderQueue','refreshTitleSelectForElement']) c[name]=()=>{throw Error(`Eager call: ${name}`);};
  const setup = prefix => {
    calls.push(['setup',prefix]);
    for(const suffix of ['ImageSet','Skill','Title','TraitSet','AttributeSet','EquipmentSet','CombatProfile','UnitProfile',...(prefix==='source'?['Base','Spawn']:[])]) {
      c.setLazySelect(prefix+suffix,()=>{throw Error('Catalog eagerly loaded');},{value:'base',label:'Base'});
    }
  };
  c.setupEditLazySelects=()=>setup('edit'); c.setupCreateLazySelects=()=>setup('source');
  return {c,node,calls};
}

for(const kind of ['patch_character','clone_character']) test(`${kind}: lazy restore preserves saved settings without changing queue`,()=>{
  const {c,node,calls}=harness();
  const payload={targetKey:'base',displayName:'',newName:'Saved new name',imageSetKey:'saved-image',subtype:'fire',
    titleSourceKey:'saved-title',attributeSetSourceKey:'attrs',combatProfileSourceKey:'donor',unitProfileSourceKey:'donor',skillSourceKey:'donor',
    sourceKeys:{base:'base',imageSet:'saved-image',title:'saved-title',attributeSet:'attrs',combatProfile:'donor',unitProfile:'donor',skill:'donor',spawn:'donor'},
    traitSet:{setKey:'trait'},equipmentSet:{setKey:'gear'},attributeSetClone:{overrides:{resolve:0}},
    unitStatClone:{overrides:{morale:37}},spawn:{weight:0,birthYear:180,minRound:7,maxRound:999,event:'delayed_join'},
    skillTree:{sourceSetKey:'skills',replacements:{old:'new'}},dedicatedArmour:{armourBonus:0,meleeDefenceBonus:12,missileDefenceBonus:-5}};
  c.state.queue=[{kind,payload}];
  const before=JSON.stringify(c.state.queue);
  c.loadQueueItem(0);
  const p=kind==='clone_character'?'source':'edit'; const f=p==='source'?'create':'edit';
  for(const [suffix,value] of Object.entries({ImageSet:'saved-image',Skill:'donor',Title:'saved-title',TraitSet:'trait',AttributeSet:'attrs',EquipmentSet:'gear',CombatProfile:'donor',UnitProfile:'donor'})) {
    assert.equal(node(p+suffix).value,value,suffix);
    assert.equal(node(p+suffix)._optionsLoaded,false,suffix);
    assert.equal(node(p+suffix)._allOptions.length,1,suffix);
  }
  assert.equal(node(p+'ImageSet')._allOptions[0].label,'Saved image');
  assert.equal(node(f+'Name').value,p==='source'?'Saved new name':'');
  for(const [suffix,value] of Object.entries({Weight:0,AgeRange:180,MinRound:7,MaxRound:999})) assert.equal(node(f+suffix).value,value,suffix);
  assert.equal(node(p+'AttrResolve').value,0);
  assert.equal(node(p+'Morale').value,37);
  assert.equal(c.state.skillTreeDrafts[p+':skills'].replacements.old,'new');
  if(p==='source') {
    assert.equal(node('sourceDedicatedArmourEnabled').checked,true);
    assert.equal(node('sourceDedicatedArmourValue').value,0);
    assert.equal(node('sourceMeleeDefenceBonus').value,12);
    assert.equal(node('sourceMissileDefenceBonus').value,-5);
  }
  assert.equal(JSON.stringify(c.state.queue),before);
  for(const name of ['renderSelectedPreview','renderValidation','renderSkillTreeEditor','updateImagePreview']) assert.equal(calls.filter(x=>x[0]===name).length,1,name);
  assert.deepEqual(calls.filter(x=>x[0]==='setup').map(x=>x[1]),[p]);
  assert.equal(calls.filter(x=>x[0]==='renderRoster').length,0);
  assert.equal(c.state.formOptionsSignature,'keep');
});

test('saved option outside lazy catalog survives opening the picker',()=>{
  const {c,node}=harness();
  c.setLazySelect('sourceImageSet',()=>[{value:'different',label:'Different'}]);
  c.restoreQueueSelect('sourceImageSet','saved-image');
  c.ensureSelectOptionsLoaded(node('sourceImageSet'));
  assert.equal(node('sourceImageSet').value,'saved-image');
  assert.ok(node('sourceImageSet')._allOptions.some(x=>x.value==='saved-image'));
});

test('summary helpers defer validation only when requested',()=>{
  let validations=0;
  const c=vm.createContext({$:()=>({value:'saved',innerHTML:''}),characters:()=>[{key:'saved'}],
    resolveAttributeChoice:()=>({key:'saved'}),equipmentSummaryMarkup:()=>'',unitSummaryMarkup:()=>'',
    attributeSummaryMarkup:()=>'',ceoSetSummaryMarkup:()=>'',bindValidationInput(){},
    ATTRIBUTE_FIELDS:[['Resolve','resolve']],renderValidation(){validations++;}});
  for(const [file,names] of [['web/app-editor.js',['syncEquipmentSummary','syncUnitSummary','syncAttributeSummary']],
    ['web/app-form-helpers.js',['syncCeoSetSummary']]]) {
    const text=fs.readFileSync(file,'utf8');
    for(const name of names) {
      const start=text.indexOf(`function ${name}(`); const end=text.indexOf('\nfunction ',start+1);
      vm.runInContext(text.slice(start,end<0?undefined:end),c);
      const args=name==='syncCeoSetSummary'?['edit','trait','id']:['edit','id'];
      const before=validations;
      c[name](...args,{deferValidation:true}); assert.equal(validations,before,name);
      c[name](...args); assert.equal(validations,before+1,name);
    }
  }
});
