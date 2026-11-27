"""Maintainer-only import. The distributed editor never needs a game install."""
from __future__ import annotations
import argparse, hashlib, json, shutil, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tk_pack_builder.adapters import adapter_for
from tk_pack_builder.web_runtime import _ensure_rpfm_server
from tk_pack_builder.ceo_ccd import CeoCcd,_top_level_record_map,_group_key,initial_ceo_active_ceos
from tk_pack_builder.pfh import read_pfh_index,read_entry_bytes
from scripts.build_assembly_kit_ui_catalogs import summarize_effect_relations

EXCLUDED_NODES={f'ep_ceo_node_career_historical_{s}_01' for s in
 ('cao_huan','liu_qi','liu_shen','sima_song','sima_yu_earth','sima_yu_metal')}
EXCLUDED_TEMPLATE='3k_mtu_template_historical_lady_buyeo_wol_hero_water'

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--game-data',type=Path,required=True)
 parser.add_argument('--mtu',type=Path,required=True)
 parser.add_argument('--mtu-korean',type=Path,required=True)
 args=parser.parse_args()
 material_path=ROOT/'work/internal_materials/vanilla_mtu/materials.v015.json'
 title_path=ROOT/'tk_pack_builder/data/assembly_kit_title_effects.ko.json'
 registry_path=ROOT/'tk_pack_builder/data/verified_ceo_registry.json'
 backup=ROOT/'work/reference-data-before-fix-2026-11-28';backup.mkdir(exist_ok=True)
 for p in (material_path,title_path,registry_path):
  if p.exists() and not (backup/p.name).exists():shutil.copy2(p,backup/p.name)
 material=json.loads(material_path.read_text(encoding='utf-8'))
 _ensure_rpfm_server();loc={};effects={};sources=[]
 for p in [args.game_data/'local_kr.pack',args.mtu,args.mtu_korean]:
  s=adapter_for('rpfm').open_pack(p)
  for path in s.list_loc_files():loc.update(s.read_loc(path))
  sources.append(str(p.resolve()))
 for t in material['tables'].values():
  if '/effects_tables/' in t['tablePath']:effects.update({r['effect']:r for r in t['rows']})
 ceos=set();nodes={};effect_lists={};thresholds={};initial_titles={};provenance=[]
 for p in [args.game_data/'fast.pack',args.mtu]:
  e=next(e for e in read_pfh_index(p).entries if e.path=='campaigns/ceo_data.ccd')
  raw=read_entry_bytes(p,e);ccd=CeoCcd.from_bytes(raw);records=_top_level_record_map(ccd.root)
  provenance.append({'pack':p.name,'ccdSha256':hashlib.sha256(raw).hexdigest()})
  ceos.update(_group_key(g) for rec in records.get('CEO_TABLE_CREATE',[]) for g in rec.groups)
  for rec in records.get('CEO_NODE_TABLE_POPULATE',[]):
   for g in rec.groups:
    key=_group_key(g)
    if key and '_ceo_node_career_' in key:nodes[key]=g
  for rec in records.get('CEO_THRESHOLD_TABLE_POPULATE',[]):
   for g in rec.groups:thresholds[_group_key(g)]=[s for n in g for nn in n.walk() for s in nn.strings()]
  for rec in records.get('INITAL_CEO_TABLE_CREATE',[]):
   for g in rec.groups:
    key=_group_key(g)
    initial_titles[key]=[k for k in initial_ceo_active_ceos(ccd,key) if '_ceo_career_' in k and '_childhood_' not in k]
  for rec in records.get('EFFECTS_LIST_TABLE_POPULATE',[]):
   for g in rec.groups:
    relations=[]
    for n in g:
     for nn in n.walk():
      if nn.record_name=='EFFECT_INFOS_BLOCK':
       for row in nn.groups:
        if len(row)<3 or row[1].marker not in (10,29):raise ValueError('Unsupported CEO effect value encoding')
        value=struct.unpack('<f',row[1].payload)[0] if row[1].marker==10 else 0.0
        relations.append({'effect':row[0].string_value,'effect_scope':row[2].string_value,'value':str(value)})
    effect_lists[_group_key(g)]=relations
 node_to_title={}
 for strings in thresholds.values():
  owners={s for s in strings if s in ceos and '_ceo_career_' in s}
  if len(owners)==1:
   for node in set(strings)&nodes.keys():node_to_title[node]=next(iter(owners))
 excluded_ceos={node_to_title[k] for k in EXCLUDED_NODES if k in node_to_title}
 title_to_nodes={}
 for node,title in node_to_title.items():
  if node not in EXCLUDED_NODES:title_to_nodes.setdefault(title,[]).append(node)
 from tk_pack_builder.web import _material_ability_effect_summaries
 tables={}
 for path,t in material['tables'].items():
  alias=path.split('/')[1].removesuffix('_tables')
  tables.setdefault(alias,[]).extend({**r,'_sourceTablePath':path} for r in t['rows'])
 ability_catalog={key:[{'summary':text}] for key,text in _material_ability_effect_summaries(tables,loc).items()}
 entries=[]
 for key in sorted(nodes.keys()-EXCLUDED_NODES):
  title=node_to_title.get(key)
  if not title:raise ValueError(f'No verified CEO owner for {key}')
  lines,structured=summarize_effect_relations(effect_lists.get(key,[]),effects,loc,ability_catalog=ability_catalog)
  node_strings=[s for n in nodes[key] for nn in n.walk() for s in nn.strings()]
  title_loc=next((s for s in node_strings if s.startswith('ceo_nodes_title_')), 'ceo_nodes_title_'+key)
  description_loc=next((s for s in node_strings if s.startswith('ceo_nodes_description_')), 'ceo_nodes_description_'+key)
  aliases=[title]+[initial for initial,titles in initial_titles.items() if titles==[title]]
  entries.append({'key':key,'keys':aliases,'ceoKey':title,
   'title':loc.get(title_loc,'칭호 정보 없음'),'description':loc.get(description_loc,''),
   'category':'바닐라·MTU 칭호','effects':lines,'effectRows':structured,'sourceKind':'verified_game'})
 registry={'schemaVersion':1,'sources':provenance,'ceoKeys':sorted(ceos),
  'nodeToTitle':{k:v for k,v in node_to_title.items() if k not in EXCLUDED_NODES},
  'titleToNodes':{k:sorted(v) for k,v in title_to_nodes.items()},
  'initialToTitles':initial_titles,'excludedTitleKeys':sorted(excluded_ceos),'excludedNodes':sorted(EXCLUDED_NODES)}
 for t in material['tables'].values():
  if '/character_generation_templates_tables/' not in t['tablePath']:continue
  fields=t['db']['table']['definition']['fields'];position=next(i for i,f in enumerate(fields) if f['name']=='key')
  t['rows']=[r for r in t['rows'] if r['key']!=EXCLUDED_TEMPLATE]
  t['db']['table']['table_data']=[r for r in t['db']['table']['table_data'] if next(iter(r[position].values()))!=EXCLUDED_TEMPLATE]
 for k in list(loc):
  if k in {f'names_{prefix}_{n}' for prefix in ('name','alt_name') for n in (962851363,962851364)}:loc.pop(k)
 material['loc']={'text/mtu_pack_editor/merged_korean.loc':{'sourcePath':';'.join(sources),'locPath':'text/mtu_pack_editor/merged_korean.loc','rows':dict(sorted(loc.items()))}}
 material['referenceDataRevision']='verified-2026-11-28'
 material['sources']=list(dict.fromkeys(material['sources']+[str((args.game_data/'local_kr.pack').resolve()),str(args.mtu_korean.resolve())]))
 for p,value in [(material_path,material),(title_path,entries),(registry_path,registry)]:p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'titles':len(entries),'ceos':len(ceos),'localisation':len(loc),'excludedTitles':len(excluded_ceos),'backup':str(backup)},ensure_ascii=False))

if __name__=='__main__':main()
