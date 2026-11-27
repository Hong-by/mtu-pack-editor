const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('Korea roster requires unique portrait, not shared model or generic face',()=>{
const c=vm.createContext({});vm.runInContext(fs.readFileSync('web/app-catalog.js','utf8'),c);
const hero={templateRow:{key:'korea_hero'},artSet:'unique_hero',portraitPath:'KRC_artsets/',portraitImagePath:'ui/characters/KRC_artsets/stills/halfbody_large/faces/hero.png',cardPath:'hero',uniform:'SAD_m_earth',details:[{gameMode:'romance',retinue:'ironic_hero_korea_earth'}]};
assert.equal(c.isTemplateVariantPoolCharacter(hero),false);
assert.equal(c.isTemplateVariantPoolCharacter({...hero,portraitImagePath:''}),true);
assert.equal(c.isTemplateVariantPoolCharacter({...hero,cardPath:'3k_main_hero_generic_male_earth_face_05',uniform:'normal'}),true);
assert.equal(c.isTemplateVariantPoolCharacter({...hero,details:[]}),true);
});
