import unittest
from tk_pack_builder.web import _attach_roster_factions

class RosterFactionTests(unittest.TestCase):
    def test_exact_template_links_multiple_factions_and_unknown(self):
        chars=[{'key':'go_yeonu'}, {'key':'unmapped'}]
        tables={'start_pos_factions':[{'ID':'1','faction':'goguryeo'},{'ID':'2','faction':'baekje'}],
                'start_pos_characters':[{'template':'go_yeonu','faction':'1'},
                    {'template':'go_yeonu','faction':'1'},{'template':'go_yeonu','faction':'2'},
                    {'template':'unmapped','faction':'missing'}]}
        _attach_roster_factions(chars,tables,{'factions_screen_name_goguryeo':'고구려'})
        self.assertEqual(chars[0]['rosterFactions'],[{'key':'baekje','label':'baekje'},{'key':'goguryeo','label':'고구려'}])
        self.assertEqual(chars[1]['rosterFactions'],[])
