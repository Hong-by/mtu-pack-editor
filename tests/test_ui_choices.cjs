const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const editor = fs.readFileSync('web/app-editor.js', 'utf8');
const appearance = fs.readFileSync('web/app-appearance.js', 'utf8');
const recipe = fs.readFileSync('web/app-recipe.js', 'utf8');
function attributeContext() {
  const row = (key, gameMode, equivalenceKey='same') => ({key,gameMode,equivalenceKey,stats:{resolve:40},label:'같은 능력치'});
  const context = vm.createContext({state:{options:{attributeSetCatalog:[
    row('3k_dlc06_nanman_records','historical'), row('3k_dlc06_nanman_romance','romance'),
    row('3k_main_records','historical'), row('3k_main_romance','romance'),
    row('other_romance','romance','different-bounds'),
    {key:'placeholder_attribute_set',stats:{}},
  ]}}, cachedDerived:(_,fn)=>fn(), attributeSetDisplayName:(_,label)=>label, characters:()=>[],
    ATTRIBUTE_FIELDS:[['Resolve','resolve','결의']], nullableNumber:Number,
    $:()=>({value:'55'}), detailsByMode:character=>Object.fromEntries(character.details.map(row=>[row.gameMode,row]))});
  vm.runInContext(editor.slice(editor.indexOf('function attributeSetChoices'),editor.indexOf('function attributeSummaryMarkup')),context);
  vm.runInContext(editor.slice(editor.indexOf('function attributeSetCloneFrom'),editor.indexOf('function attributePatchDescription')),context);
  vm.runInContext(recipe.slice(recipe.indexOf('function attributeClonesForRecipe')),context);
  return context;
}
test('equivalent sets collapse, missing values disappear, differing bounds stay separate',()=>{
  const c=attributeContext();
  assert.equal(vm.runInContext('attributeSetChoices().length',c),2);
  assert.equal(vm.runInContext("resolveAttributeChoice('attribute_set::3k_dlc06_nanman_records').attributeSet",c),'3k_main_romance');
  assert.equal(vm.runInContext("resolveAttributeChoice('3k_main_records').details[0].attributeSet",c),'3k_main_records');
});
test('editing a grouped set emits distinct mode clones and supports legacy queue payloads',()=>{
  const c=attributeContext();
  vm.runInContext("var clone=attributeSetCloneFrom('edit',resolveAttributeChoice('3k_main_records'),'test',1)",c);
  assert.equal(vm.runInContext('attributeClonesForRecipe(clone).length',c),2);
  assert.equal(vm.runInContext("clone.modeClones.find(c=>c.gameMode==='historical').sourceSetKey",c),'3k_main_records');
  assert.equal(vm.runInContext("attributeCloneKeyForMode(clone,'romance')",c),'3k_main_attribute_set_general_hby_test_1_romance');
  assert.equal(vm.runInContext("attributeCloneKeyForMode(clone,'historical')",c),'3k_main_attribute_set_general_hby_test_1_records');
  assert.equal(vm.runInContext('clone.modeClones[0].overrides.resolve',c),55);
  assert.equal(vm.runInContext("attributeCloneKeyForMode({newSetKey:'old'},'historical')",c),'old');
});
test('image grouping requires full asset and age/season equality, not thumbnail equality',()=>{
  const c=vm.createContext({});
  vm.runInContext(appearance.slice(appearance.indexOf('function imageChoiceIdentity'),appearance.indexOf('function mergeImageOnlyAppearance')),c);
  const result=vm.runInContext(`
    const image = {key:'a', imageAssets:[{path:'ui/full.png',sourcePath:'pack1'}], rows:[{age:16,season:'none',portrait:'p',card:'c'}], portraitImagePath:'same.png'};
    const copy = {...image,key:'b'};
    const variant = {...image,key:'c',rows:[{age:60,season:'none',portrait:'p',card:'c'}]};
    const source = {...image,key:'d',imageAssets:[{path:'ui/full.png',sourcePath:'pack2'}]};
    dedupeImageChoices([image,copy,variant,source]);
  `,c);
  assert.equal(result.length,3);
  assert.equal(result[0].imageAliases.join(','),'a,b');
});

test('title aliases collapse while keeping the selected key and different CEO identities',()=>{
  const titles = {a:{titleCeoKey:'same',titleEffectSummary:'결의 +5'}, b:{titleCeoKey:'same',titleEffectSummary:'결의 +5'}, c:{titleCeoKey:'other',titleEffectSummary:'결의 +5'}};
  const c=vm.createContext({document:{addEventListener(){}},resolveTitleChoice:key=>titles[key]});
  vm.runInContext(fs.readFileSync('web/app-discovery.js','utf8'),c);
  const result=vm.runInContext("dedupePickerOptions({id:'editTitle',value:'b'},[{value:'a'},{value:'b'},{value:'c'}])",c);
  assert.equal(result.length,2);
  assert.equal(result[0].value,'b');
  assert.equal(result[1].value,'c');
});
