const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
test('faction intersects gender, element and favorites, with explicit unknown',()=>{
 const c=vm.createContext({state:{filter:'wood',rosterFaction:'goguryeo',workflowGender:'male',favoritesOnly:false},ELEMENTS:{wood:{}},matchesGender:(x,g)=>x.gender===g});
 vm.runInContext(fs.readFileSync('web/app-catalog.js','utf8'),c);
 const hero={gender:'male',element:'wood',rosterFactions:[{key:'goguryeo',label:'고구려'}]};
 assert(c.matchesRosterFilter(hero));
 assert(!c.matchesRosterFilter({...hero,element:'fire'}));
 assert(!c.matchesRosterFilter({...hero,gender:'female'}));
 assert(!c.matchesRosterFilter({...hero,rosterFactions:[]}));
 c.state.rosterFaction='unknown';
 assert(!c.matchesRosterFilter(hero));
 assert(c.matchesRosterFilter({...hero,rosterFactions:[]}));
 c.state.rosterFaction='all';
 assert(c.matchesRosterFilter(hero));
});
