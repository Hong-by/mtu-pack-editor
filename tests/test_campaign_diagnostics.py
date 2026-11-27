import unittest

from tk_pack_builder.campaign_script import build_campaign_start_script
from tk_pack_builder.delta_builder import _campaign_start_spawn_script, _lua_escape, _lua_string_list
from tk_pack_builder.recipe import CharacterPatch

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None


MOCK = r'''
logs, persisted, calls, saved, characters = {}, {}, {}, {}, {old=true}
io = {open=function()
    local text
    return {write=function(self, s) text=s end, flush=function() end,
        close=function() table.insert(persisted, text) end}
end}
output=function(s) table.insert(logs,s) end
local function record(s)
    table.insert(calls,s)
    assert(string.find(persisted[#persisted], 'status=before', 1, true))
end
local manager = {
    add_ceo=function(self,key) record('add:'..key); return true end,
    remove_ceos=function(self,key) record('remove:'..key); return true end
}
local character = {is_null_interface=function() return false end,
    is_dead=function() return false end,
    faction=function() return {name=function() return 'player' end} end,
    is_faction_leader=function() return false end,
    ceo_management=function() return manager end}
local faction = {ceo_management=function() return manager end,
    create_character_from_template=function(self,kind,subtype,key,random)
        record('spawn:'..key)
        assert(kind=='general' and random==false)
        if fail_spawn then error('mock spawn failure') end
        characters[key]=true
    end}
cm = {
    add_first_tick_callback=function(self,cb) first_tick=cb end,
    get_local_faction=function() return 'player' end,
    turn_number=function() return 1 end,
    get_saved_value=function(self,k) return saved[k] end,
    set_saved_value=function(self,k,v) saved[k]=v end,
    query_model=function() return {character_for_template=function(self,key)
        if characters[key] then return character end
    end} end,
    modify_faction=function() return faction end,
    modify_character=function() return character end
}
core={add_listener=function() end}
'''


def script():
    return build_campaign_start_script(
        [dict(template='new', subtype='fire', event='campaign_start', saveKey='spawn', attemptKey='attempt')],
        [dict(template=key, saveKey='ceo_'+key, removeCeos=['old_trait'], addCeos=['new_trait']) for key in ['old', 'new']],
        [dict(template=key, saveKey='eq_'+key, grantKey='grant_'+key, grantEquipmentCeos=['weapon']) for key in ['old', 'new']],
        work_entries=[dict(template='new', kind='new_character'), dict(template='old', kind='existing_character')],
        escape=_lua_escape, string_list=_lua_string_list,
    )


class DiagnosticTests(unittest.TestCase):
    def test_db_only_patch_has_manifest_without_spawn(self):
        text = _campaign_start_spawn_script([], [CharacterPatch(template_key='old', template_overrides={}, detail_overrides={})])
        self.assertIn('hby_diag_kinds["old"] = "existing_character"', text)
        self.assertNotIn('template = "old"', text)
        self.assertIn('work_manifest', text)

    @unittest.skipIf(LuaRuntime is None, 'Install lupa to execute Lua 5.1 runtime checks')
    def test_mixed_operations_and_persisted_before_markers(self):
        lua = LuaRuntime()
        lua.execute(MOCK)
        lua.execute(script())
        lua.execute('first_tick()')
        calls = list(lua.globals().calls.values())
        self.assertEqual(calls, ['spawn:new', 'add:weapon', 'add:weapon', 'remove:old_trait', 'add:new_trait', 'remove:old_trait', 'add:new_trait'])
        logs = '\n'.join(lua.globals().persisted.values())
        self.assertIn('kind=new_character template=new stage=hby_spawn_one.call_1 status=before', logs)
        self.assertIn('kind=existing_character template=old stage=hby_add_ceo.call_1 status=before detail=ceo=new_trait', logs)
        self.assertIn('stage=first_tick.call_1 status=after detail=pcall_ok=true', logs)
        lua.execute('first_tick()')
        self.assertEqual(list(lua.globals().calls.values()), calls)

    @unittest.skipIf(LuaRuntime is None, 'Install lupa to execute Lua 5.1 runtime checks')
    def test_failed_call_and_logging_failure_do_not_escape(self):
        lua = LuaRuntime()
        lua.execute(MOCK + '\nfail_spawn=true')
        lua.execute(script())
        lua.execute('first_tick()')
        self.assertIn('stage=hby_spawn_one.call_1 status=after detail=pcall_ok=false', '\n'.join(lua.globals().persisted.values()))
        lua = LuaRuntime()
        lua.execute(MOCK + '\nio=nil; output=function() error("logger failed") end')
        # DB-only operations need no native calls, even when both log sinks fail.
        text = _campaign_start_spawn_script([], [CharacterPatch(template_key='old', template_overrides={}, detail_overrides={})])
        lua.execute(text)
        lua.execute('first_tick()')


if __name__ == '__main__':
    unittest.main()
