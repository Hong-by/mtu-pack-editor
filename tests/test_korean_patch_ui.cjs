const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('web/app-appearance.js','utf8');
test('catalogue labels remain the patched names even when sheet fallback disagrees',()=>{
 const ctx=vm.createContext({sheetTitleInfoFor:()=>({krTitle:'예전 이름'}),hasHangul:s=>/[가-힣]/.test(s),looksLikeInternalKey:()=>false,isMixedNameTitleLabel:()=>false,looksLikeSlugLabel:()=>false});
 vm.runInContext(source.slice(source.indexOf('function displayTitleLabel('),source.indexOf('function cleanTitleOwnerName(')),ctx);
 assert.equal(vm.runInContext("displayTitleLabel('절천야차','3k_main_ceo_node_career_historical_he_man_01')",ctx),'절천야차');
 assert.equal(vm.runInContext("fallbackTitleDisplayName('절천야차','key','하만')",ctx),'절천야차');
});
