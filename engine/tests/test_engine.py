import json
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
BIN=Path(__file__).resolve().parents[2]/'build'/'bluff_engine'
def call(value):
    p=subprocess.run([str(BIN)],input=json.dumps(value),text=True,capture_output=True)
    return p.returncode,json.loads(p.stdout)
class EngineTests(unittest.TestCase):
    def test_existing_policy_artifacts_unchanged(self):
        root=BIN.parents[1]
        expected={'fixed5_cfr.json':'9054a212e2865189ee9358e344e3fba48298408edb96fbf8cc343e75d005b977',
                  'fixed5_cfr_v2.json':'d99c9c002989c65fed62348b8ea623974436b7ebc75f9a0821c6e5edee99d9a8'}
        for name,digest in expected.items():
            self.assertEqual(hashlib.sha256((root/'policies'/name).read_bytes()).hexdigest(),digest)
    def fresh(self,seed=4):return call({'op':'new','n':5,'seed':seed,'agent':'probability','auto_ai':False})[1]['state']
    def step(self,s,a):
        code,out=call({'op':'step','state':s,'action':a});self.assertEqual(code,0,out);return out['state']
    def test_fixed_five_and_private_view(self):
        s=self.fresh();v=call({'op':'view','state':s})[1]['view']
        self.assertEqual(v['counts'],[5,5]);self.assertEqual(v['scores'],[0,0]);self.assertEqual(len(v['hand']),5)
        self.assertIsNone(v['ai_hand']);self.assertNotIn('rng',v);self.assertNotIn('hands',v)
        self.assertEqual(len(v['legal_actions']),60 if s['turn']==0 else 0)
        self.assertEqual(s,self.fresh())
        starters={self.fresh(seed)['starter'] for seed in range(20)}
        self.assertEqual(starters,{0,1})
    def test_quantity_only_raise_and_forced_call(self):
        s=self.fresh();s=self.step(s,{'type':'bid','q':3,'f':4})
        for bid in ({'type':'bid','q':3,'f':5},{'type':'bid','q':2,'f':6}):
            code,out=call({'op':'step','state':s,'action':bid});self.assertNotEqual(code,0);self.assertIn('quantity must increase',out['error'])
        self.assertIn({'type':'bid','q':4,'f':1},call({'op':'legal','state':s})[1]['actions'])
        s=self.step(s,{'type':'bid','q':10,'f':3})
        self.assertEqual(call({'op':'legal','state':s})[1]['actions'],[{'type':'call'}])
    def test_scoring_and_explicit_next_round(self):
        s=self.fresh();starter=s['turn'];s['hands']=[[1]*5,[2]*5]
        s=self.step(s,{'type':'bid','q':6,'f':1});s=self.step(s,{'type':'call'})
        self.assertEqual(s['phase'],'ROUND_OVER');self.assertEqual(s['scores'][1-starter],1)
        self.assertEqual(s['counts'],[5,5]);self.assertEqual(s['round'],1)
        self.assertEqual(s['next_starter'],starter)
        code,out=call({'op':'step','state':s,'action':{'type':'bid','q':1,'f':1}});self.assertNotEqual(code,0)
        s=call({'op':'next_round','state':s,'auto_ai':False})[1]['state']
        self.assertEqual(s['round'],2);self.assertEqual(s['phase'],'BIDDING');self.assertEqual(s['turn'],starter)
        self.assertEqual(s['counts'],[5,5]);self.assertEqual(s['scores'][1-starter],1)
    def test_full_match_replay_and_round_count(self):
        s=self.fresh(8)
        for _ in range(300):
            if s['status']=='COMPLETED':break
            if s['phase']=='ROUND_OVER':s=call({'op':'next_round','state':s,'auto_ai':False})[1]['state'];continue
            action=next((a for a in call({'op':'legal','state':s})[1]['actions'] if a['type']=='call'),{'type':'bid','q':10,'f':1})
            s=self.step(s,action)
        self.assertEqual(s['status'],'COMPLETED');self.assertEqual(max(s['scores']),5)
        self.assertGreaterEqual(s['round'],5);self.assertLessEqual(s['round'],9)
        self.assertEqual(s['counts'],[5,5])
        self.assertTrue(call({'op':'replay','state':s})[1]['valid'])
    def test_probability_edges(self):
        for q,expected in ((1,1.0),(7,0.0)):
            self.assertEqual(call({'op':'prior','q':q,'f':2,'hand':[2],'unknown':5})[1]['probability'],expected)
        self.assertAlmostEqual(call({'op':'prior','q':2,'f':2,'hand':[2],'unknown':1})[1]['probability'],1/6)
    def test_public_claim_history(self):
        opened=call({'op':'new','n':5,'seed':123,'agent':'probability'})[1]
        self.assertEqual(opened['view']['turn'],'HUMAN')
        self.assertTrue(any(e.get('player')=='AI' for e in opened['view']['events'] if e['type']=='bid'))
        human_bid=next(a for a in opened['view']['legal_actions'] if a['type']=='bid')
        replied=call({'op':'act','state':opened['state'],'action':human_bid})[1]
        self.assertTrue(any(e.get('player')=='HUMAN' for e in replied['view']['events'] if e['type']=='bid'))
        self.assertTrue(all('hands' not in e for e in replied['view']['events'] if e['type']!='reveal'))
    def test_ai_decision_record_uses_only_its_hand_and_stays_private(self):
        opened=call({'op':'new','n':5,'seed':123,'agent':'cfr'})[1]
        self.assertNotIn('ai_decisions',opened['view'])
        self.assertTrue(opened['state']['ai_decisions'])
        decision=opened['state']['ai_decisions'][0]
        self.assertEqual(decision['hand'],opened['state']['hands'][1])
        self.assertIsNone(decision['current_bid_truth_prior'])
        action=decision['action']
        expected=call({'op':'prior','q':action['q'],'f':action['f'],'hand':decision['hand'],'unknown':5})[1]['probability']
        self.assertAlmostEqual(decision['action_truth_prior'],expected)
        self.assertTrue(0<=decision['policy_probability']<=1)
        self.assertTrue(decision['policy_options'])
        self.assertTrue(all(0<=item['weight']<=1 for item in decision['policy_options']))
    def test_trained_agents_choose_legal_actions(self):
        hits={'cfr':0,'adaptive':0,'cfr2':0,'mccfr_external_v1':0}
        for agent in hits:
            for seed in range(30,40):
                s=call({'op':'new','n':5,'seed':seed,'agent':agent,'agent_human':'probability','auto_ai':False})[1]['state']
                for _ in range(100):
                    if s['status']=='COMPLETED':break
                    if s['phase']=='ROUND_OVER':
                        s=call({'op':'next_round','state':s,'auto_ai':False})[1]['state'];continue
                    legal=call({'op':'legal','state':s})[1]['actions']
                    code,out=call({'op':'bot_step','state':s})
                    self.assertEqual(code,0,out)
                    self.assertIn(out['action'],legal)
                    hits[agent]+=bool(out['policy_hit'])
                    s=out['state']
                self.assertEqual(s['status'],'COMPLETED')
                self.assertTrue(call({'op':'replay','state':s})[1]['valid'])
        self.assertGreater(hits['cfr'],0)
        self.assertGreater(hits['adaptive'],0)
        self.assertGreater(hits['cfr2'],0)
        self.assertGreater(hits['mccfr_external_v1'],0)
    def test_ai_choice_does_not_use_hidden_human_dice(self):
        for agent in ('probability','cfr','adaptive','cfr2','mccfr_external_v1'):
            s=call({'op':'new','n':5,'seed':42,'agent':agent,'auto_ai':False})[1]['state']
            s['turn']=1
            variants=[]
            for hidden in ([1]*5,[6]*5):
                changed=json.loads(json.dumps(s));changed['hands'][0]=hidden
                code,out=call({'op':'bot_step','state':changed})
                self.assertEqual(code,0,out)
                variants.append(out['action'])
            self.assertEqual(variants[0],variants[1],agent)
    def test_mccfr_corrupt_policy_uses_legal_fallback(self):
        s=call({'op':'new','n':5,'seed':42,'agent':'mccfr_external_v1','auto_ai':False})[1]['state']
        s['turn']=1
        with tempfile.TemporaryDirectory() as folder:
            policy_dir=Path(folder)/'policies';policy_dir.mkdir()
            (policy_dir/'mccfr_external_v1.bin').write_bytes(b'corrupt')
            result=subprocess.run([str(BIN)],cwd=folder,input=json.dumps({'op':'bot_step','state':s}),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout)
            out=json.loads(result.stdout)
            self.assertFalse(out['policy_hit'])
            self.assertIn(out['action'],call({'op':'legal','state':s})[1]['actions'])
    def test_adaptive_models_opponent_in_either_seat(self):
        s=call({'op':'new','n':5,'seed':42,'agent':'probability','agent_human':'adaptive','auto_ai':False})[1]['state']
        s['starter']=0;s['turn']=0;s['bid']={'q':2,'f':2};s['bidder']=1
        s['hands'][0]=[2,1,1,3,4];s['policy_rng']=2
        def action(bidder,truth):
            changed=json.loads(json.dumps(s))
            changed['events']=[{'type':'reveal','bidder':bidder,'true':truth} for _ in range(3)]
            code,out=call({'op':'bot_step','state':changed})
            self.assertEqual(code,0,out)
            return out['action']
        self.assertEqual(action('AI',False),{'type':'call'})
        self.assertEqual(action('AI',True)['type'],'bid')
        self.assertEqual(action('HUMAN',False),action('HUMAN',True))
if __name__=='__main__':unittest.main()
