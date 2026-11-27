const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function context() {
  const c = vm.createContext({compactObject: x => x});
  for (const f of ['app-appearance.js', 'app-workflow.js']) vm.runInContext(fs.readFileSync(`web/${f}`, 'utf8'), c);
  return c;
}
function donor() {
  const root = 'ui/characters/donor_folder';
  return {portraitPath:'donor_folder/', cardPath:'actual_face', imageAssets:[
    ...['bobbleheads','halfbody_large','halfbody_small','mini','unitcards'].flatMap(kind =>
      ['', 'large/'].map(size => ({path:`${root}/stills/${kind}/${size}actual_face.png`, sourcePath:'source'}))),
    {path:`${root}/composites/large_panel/norm/norm.png`,sourcePath:'source'},
    {path:`${root}/composites/faces/actual_face/large_panel/norm/noanim.png`,sourcePath:'source'},
    {path:`${root}/stills/bobbleheads/armour_overlay.png`,sourcePath:'source'},
  ]};
}
test('folder and card mismatch retargets all ten stills and supplies generic faces', () => {
  const a=context().customImageAssetsFromAppearance(donor(),'new_face');
  for (const kind of ['bobbleheads','halfbody_large','halfbody_small','mini','unitcards']) {
    for (const size of ['', 'large/']) for (const face of ['', 'faces/']) {
      assert(a.some(x=>x.targetPath===`ui/characters/new_face/stills/${kind}/${face}${size}new_face.png`));
    }
  }
  assert(!a.some(x=>x.targetPath.includes('actual_face')));
  assert(a.some(x=>x.targetPath.endsWith('/armour_overlay.png')));
  assert.equal(new Set(a.map(x=>x.targetPath)).size,a.length);
});
test('Korea male patch retains armour layers and EMPTY without changing donor art', () => {
  const c=context(), path='ui/characters/KRC_artsets/stills/bobbleheads/3k_main_ancillary_armour_medium_leather_common_shared_male.png';
  const target={portraitPath:'KRC_artsets/',isMale:true,imageAssets:[{path,sourcePath:'korea'}]};
  const a=c.patchImageAssetsFromAppearance(donor(),target,'new_face','new_face');
  assert(a.some(x=>x.sourcePath==='korea' && x.targetPath==='ui/characters/new_face/stills/bobbleheads/EMPTY.png'));
  assert(a.some(x=>x.sourcePath==='korea' && x.targetPath.includes('new_face/stills/bobbleheads/3k_main_ancillary_armour_')));
  assert(!c.patchImageAssetsFromAppearance(donor(),{...target,isMale:false},'new_face','new_face').some(x=>x.sourcePath==='korea'));
});

test('a composite preview never becomes the card filename', () => {
  const c=context(), a={...donor(),cardPath:'donor_folder',cardImagePath:'ui/characters/donor_folder/composites/large_panel/norm/noanim.png'};
  assert.equal(c.imageCardKeyFromAppearance(a),'actual_face');
  assert(c.customImageAssetsFromAppearance(a,'new').some(x=>x.targetPath==='ui/characters/new/stills/bobbleheads/new.png'));
});

test('verified duplicate content groups choices while preserving every saved alias', () => {
  const c=context();
  const list=c.dedupeImageChoices([{key:'saved_a',name:'갑',imageContentSignature:'same'}, {key:'saved_b',name:'을',imageContentSignature:'same'}, {key:'different',imageContentSignature:'other'}]);
  assert.equal(list.length,2);
  assert.equal(list[0].imageAliases.join(','),'saved_a,saved_b');
  assert.equal(list[0].imageAliasNames.join(','),'갑,을');
});
