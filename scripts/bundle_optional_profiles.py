"""Explicit maintainer import of optional mod data; no runtime game-path lookup."""
import argparse, base64, copy, hashlib, json, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tk_pack_builder.adapters import adapter_for
from tk_pack_builder.web_runtime import _ensure_rpfm_server
from tk_pack_builder.ceo_ccd import CeoCcd, _top_level_record_map, _group_key, initial_ceo_active_ceos
from tk_pack_builder.pfh import read_pfh_index, read_entry_bytes
from tk_pack_builder.delta_builder import _db_with_rows
from tk_pack_builder.source_profiles import using, directory
from scripts.bundle_verified_reference_data import EXCLUDED_NODES
from scripts.build_assembly_kit_ui_catalogs import summarize_effect_relations

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True),encoding='utf-8')

def bundle_portraits(pack, folder):
    """Copy portrait assets into the portable bundle, not the user's game."""
    for entry in read_pfh_index(pack).entries:
        if not entry.path.startswith('ui/characters/') or not entry.path.lower().endswith(('.png','.jpg','.jpeg','.dds')):
            continue
        target=ROOT/'work/assets'/folder/entry.path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(read_entry_bytes(pack,entry))

def catalog(material, raw, blocked):
    ccd=CeoCcd.from_bytes(raw)
    # Invalid legacy byte keys remain losslessly readable, but cannot be safely
    # offered to the UTF-8 DB/Lua generator.
    records=_top_level_record_map(ccd.root)
    ceos={_group_key(g) for r in records.get('CEO_TABLE_CREATE',[]) for g in r.groups}
    bad={k for k in ceos if any(0xDC80<=ord(c)<=0xDCFF for c in k)}
    # Mods can use the career key itself as the node key. Ownership comes
    # from the threshold relations, not from a vanilla naming convention.
    nodes={_group_key(g):g for r in records.get('CEO_NODE_TABLE_POPULATE',[]) for g in r.groups}
    owners={}
    for r in records.get('CEO_THRESHOLD_TABLE_POPULATE',[]):
        for g in r.groups:
            strings={s for n in g for nn in n.walk() for s in nn.strings()}
            titles={s for s in strings & ceos if '_ceo_career_' in s}
            if len(titles)==1:
                for node in strings & nodes.keys():owners[node]=next(iter(titles))
    initial={_group_key(g):[k for k in initial_ceo_active_ceos(ccd,_group_key(g)) if '_ceo_career_' in k and '_childhood_' not in k] for r in records.get('INITAL_CEO_TABLE_CREATE',[]) for g in r.groups}
    excluded={owners[k] for k in EXCLUDED_NODES if k in owners}|bad
    effects={};loc={};tables={}
    for entry in material['loc'].values():loc.update(entry['rows'])
    for path,t in material['tables'].items():
        alias=path.split('/')[1].removesuffix('_tables')
        tables.setdefault(alias,[]).extend(t['rows'])
        if alias=='effects':effects.update({r['effect']:r for r in t['rows']})
    from tk_pack_builder.korean_patch import overlay
    loc = overlay(loc)
    from tk_pack_builder.web import _material_ability_effect_summaries
    abilities={k:[{'summary':v}] for k,v in _material_ability_effect_summaries(tables,loc).items()}
    relations={}
    for r in records.get('EFFECTS_LIST_TABLE_POPULATE',[]):
        for g in r.groups:
            rel=[]
            for n in g:
                for nn in n.walk():
                    if nn.record_name=='EFFECT_INFOS_BLOCK':
                        for row in nn.groups:
                            if row[1].marker not in (10,29):raise ValueError('Unknown effect encoding')
                            rel.append({'effect':row[0].string_value,'effect_scope':row[2].string_value,'value':str(struct.unpack('<f',row[1].payload)[0] if row[1].marker==10 else 0)})
            relations[_group_key(g)]=rel
    entries=[]; title_nodes={}
    for node,g in sorted(nodes.items()):
        title=owners.get(node)
        if not title or title in excluded or node in EXCLUDED_NODES:continue
        if any(r['effect'] in blocked for r in relations.get(node,[])):
            excluded.add(title);blocked.add(title);continue
        title_nodes.setdefault(title,[]).append(node)
        strings=[s for n in g for nn in n.walk() for s in nn.strings()]
        titleloc=next((s for s in strings if s.startswith('ceo_nodes_title_')), 'ceo_nodes_title_'+node)
        descloc=next((s for s in strings if s.startswith('ceo_nodes_description_')), 'ceo_nodes_description_'+node)
        lines,structured=summarize_effect_relations(relations.get(node,[]),effects,loc,ability_catalog=abilities)
        entries.append({'key':node,'keys':[title]+[k for k,v in initial.items() if v==[title]],'ceoKey':title,'title':loc.get(titleloc,'칭호 정보 없음'),'description':loc.get(descloc,''),'category':'검증된 추가 모드 칭호','effects':lines,'effectRows':structured,'sourceKind':'verified_game'})
    return entries, {'schemaVersion':2,'ceoKeys':sorted(ceos-bad),'nodeToTitle':{k:v for k,v in owners.items() if v not in excluded and k not in EXCLUDED_NODES},'titleToNodes':title_nodes,'initialToTitles':initial,'excludedTitleKeys':sorted(excluded),'blockedKeys':sorted(blocked|bad),'ccdSha256':hashlib.sha256(raw).hexdigest()}

def quarantine(material, raw):
    blocked={'3k_main_template_historical_yan_xiang_hero_water','3k_mod_patriotic_solidarity'}
    ccd=CeoCcd.from_bytes(raw);records=_top_level_record_map(ccd.root)
    initials={_group_key(g) for r in records.get('INITAL_CEO_TABLE_CREATE',[]) for g in r.groups}
    badinitials={k for k in initials if any(0xDC80<=ord(c)<=0xDCFF for c in k)}
    # Block templates whose initial CEO does not exist in this effective CCD.
    for path,t in material['tables'].items():
        if '/character_generation_template_game_mode_details_tables/' in path:
            for row in t['rows']:
                k=row.get('initial_ceos')
                if k and (k not in initials or k in badinitials):blocked.add(row['character_generation_template'])
    removed=[]
    # Follow dependency direction only. A junction's other key is not itself
    # broken merely because its owner was quarantined.
    dependencies={
      'special_ability_phases': (('phase_display',), ('id',)),
      'special_ability_to_special_ability_phase_junctions': (('phase',), ('special_ability',)),
      'effect_bonus_value_unit_ability_junctions': (('unit_ability',), ('effect',)),
      'character_skill_level_to_effects_junctions': (('effect_key',), ('character_skill_key',)),
      'character_skill_nodes': (('character_skill_key',), ('key','character_skill_node_set_key')),
      'character_generation_template_game_mode_details': (('skill_set_override','retinue','initial_ceos'), ('character_generation_template',)),
      'land_units_to_unit_abilites_junctions': (('ability',), ('land_unit',)),
      'main_units': (('land_unit',), ('unit',)),
      'retinue_slot_initial_units': (('initial_unit_record',), ('retinue',)),
    }
    while True:
        changed=False
        for path,t in material['tables'].items():
            dep=dependencies.get(path.split('/')[1].removesuffix('_tables'))
            if not dep:continue
            for row in t['rows']:
                if any(row.get(field) in blocked for field in dep[0]):
                    for field in dep[1]:
                        value=row.get(field)
                        if isinstance(value,str) and value and value not in blocked:
                            blocked.add(value);changed=True
        if not changed:break
    for path,t in material['tables'].items():
        kept=[]
        for row in t['rows']:
            if any(isinstance(v,str) and v in blocked for v in row.values()):removed.append({'table':path,'row':row})
            else:kept.append(row)
        t['rows']=kept
    for t in material['tables'].values():t['db']=_db_with_rows(t['db'],t['rows'])
    return blocked,removed

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workshop',type=Path,required=True)
    parser.add_argument('--game',type=Path,required=True,help='Explicit maintainer source for base name tables')
    args=parser.parse_args();_ensure_rpfm_server()
    material=json.loads((directory('vanilla-mtu-v1')/'materials.v015.json').read_text(encoding='utf-8'))
    # Flatten by actual DB primary key, applying higher-priority layers last.
    merged={}; schemas={}; loc={}
    def merge(path,rows,db):
        family=path.split('/')[1]
        # An empty higher-priority file does not erase lower-priority rows,
        # and must not erase the cell type template needed to write them.
        if rows or family not in schemas:
            schemas[family]=db
        keys=[f['name'] for f in db['table']['definition']['fields'] if f.get('is_key')]
        for row in rows:
            identity=tuple(str(row.get(k,'')) for k in keys) if keys else json.dumps(row,sort_keys=True)
            merged.setdefault(family,{})[identity]=row
    for path,t in sorted(material['tables'].items(),reverse=True):merge(path,t['rows'],t['db'])
    base_session=adapter_for('rpfm').open_pack(args.game/'data/database.pack')
    for path in base_session.list_tables():
        if path.split('/')[1] in {'names_groups_tables','name_orders_tables','faction_to_name_groups_tables'}:
            rows=base_session.read_table(path)
            merge(path,rows,base_session.decoded_db_by_path[path])
    for t in material['loc'].values():loc.update(t['rows'])
    sources=list(material['sources']); provenance=[];raw=None; sessions=[base_session]
    undecoded=[]; imported=[]
    for ident in [2875547086,3010906135,3240150507,3242244024,3415534775]:
        path=next((args.workshop/str(ident)).glob('*.pack'))
        if ident in (2875547086,3415534775):
            bundle_portraits(path, 'profile_190' if ident==2875547086 else 'profile_korea')
        session=adapter_for('rpfm').open_pack(path)
        sessions.append(session)
        for table in sorted(session.list_tables(),reverse=True):
            if not table.startswith('db/'):continue
            try:
                rows=session.read_table(table)
                decoded=session.decoded_db_by_path[table]['table']
                from tk_pack_builder.rpfm_fields import field_names
                width=len(field_names(decoded))
                if any(len(row)!=width for row in decoded['table_data']):
                    raise ValueError('Decoded row width does not match the schema')
            except ValueError as error:
                # Preserve unsupported legacy source bytes for audit instead of
                # silently dropping them or guessing a different table layout.
                entry=next(e for e in read_pfh_index(path).entries if e.path==table)
                undecoded.append({'pack':path.name,'table':table,'reason':str(error),
                                  'base64':base64.b64encode(read_entry_bytes(path,entry)).decode('ascii')})
                print('Preserved undecoded table:',path.name,table,flush=True)
                continue
            merge(table,rows,session.decoded_db_by_path[table])
            imported.append({'pack':path.name,'table':table,'rows':len(rows)})
        for name in sorted(session.list_loc_files(),reverse=True):loc.update(session.read_loc(name))
        sources.append(path.name)
        provenance.append({'file':path.name,'size':path.stat().st_size,'mtimeNs':path.stat().st_mtime_ns})
        for entry in read_pfh_index(path).entries:
            if entry.path=='campaigns/ceo_data.ccd':raw=read_entry_bytes(path,entry)
        if ident not in [3242244024,3415534775]:continue
        profile='190' if ident==3242244024 else '190-korea'
        folder=directory(profile);folder.mkdir(parents=True,exist_ok=True)
        bundle=copy.deepcopy(material)
        bundle['sourceProfile']=profile;bundle['sources']=sources.copy();bundle['provenance']=provenance.copy()
        bundle['tables']={}
        for family,rows in merged.items():
            name='db/'+family+'/data__'; values=list(rows.values())
            bundle['tables'][name]={'tablePath':name,'rows':values,'db':_db_with_rows(schemas[family],values)}
        bundle['loc']={'text/db/profile_ko.loc':{'rows':loc.copy()}}
        blocked,removed=quarantine(bundle,raw)
        titles,registry=catalog(bundle,raw,blocked)
        # Fail closed if quarantined records leak back into generation sources.
        write(folder/'verified_ceo_registry.json',registry)
        write(folder/'assembly_kit_title_effects.ko.json',titles)
        write(folder/'materials.v015.json',bundle)
        write(folder/'undecoded_source_tables.json',undecoded)
        write(folder/'audit.json',{'sources':provenance,'importedTables':imported,'undecodedTables':[{k:v for k,v in t.items() if k!='base64'} for t in undecoded],'excludedKeys':sorted(blocked),'removedRows':removed,'titles':len(titles),'rows':sum(len(t['rows']) for t in bundle['tables'].values())})
        with using(profile):
            from tk_pack_builder.internal_materials import MaterialPackSession
            MaterialPackSession.open(folder/'materials.v015.json')
        print(profile,'titles',len(titles),'blocked',len(blocked),'rows removed',len(removed),flush=True)
    for session in sessions:session.close()

if __name__=='__main__':main()
