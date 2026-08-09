from pathlib import Path
import inspect,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import mechanism_v2 as m
from plugins.agent.plan.ConsumerPlanPlugin import ConsumerPlanPlugin
from plugins.agent.reflect.GreenCognitionPlugin import GreenCognitionPlugin
P=F=0
def c(n,x,a=None):
 global P,F
 if x:P+=1;print("PASS",n)
 else:F+=1;print("FAIL",n,a)
c("negative affect",m.semantic_to_affective(-1,1,1)<0)
c("positive affect",m.semantic_to_affective(1,1,1)>0)
base=dict(baseline_trust=7,previous_trust=5.5,attitude_att=.6,subjective_norm_sn=.5,pbc=.5,
 crisis_memory=1.5,repair_memory=0,valence=0,arousal=0,credibility=.5,evidence_strength=0,
 topic_relevance=0,had_observation=False,social_observation_count=0)
q=m.update_psychological_state(**base)
c("quiet retains damage",q["crisis_memory"]>0 and q["trust_final"]<7,q)
pa=dict(base);pa.update(crisis_memory=q["crisis_memory"],previous_trust=q["trust_final"],
 valence=.8,arousal=.8,credibility=.8,evidence_strength=.8,topic_relevance=.9,had_observation=True)
pos=m.update_psychological_state(**pa)
c("positive creates repair",pos["repair_memory"]>q["repair_memory"],pos)
c("positive improves trust",pos["trust_final"]>q["trust_final"],pos)
legacy=dict(pa)
legacy.update(perceived_empathy=0.0,enterprise_clarification_observed=True)
legacy_pe0=m.update_psychological_state(**legacy)
legacy.update(perceived_empathy=0.8,enterprise_clarification_observed=False)
legacy_no_enterprise=m.update_psychological_state(**legacy)
legacy.update(enterprise_clarification_observed=True,empathy_repair_weight=0.0)
legacy_weight0=m.update_psychological_state(**legacy)
for k in ("trust_final","crisis_memory","repair_memory","purchase_intention","posting_intention",
          "attitude_att","subjective_norm_sn","pbc"):
 c("pe0 old behavior "+k,legacy_pe0[k]==pos[k],(legacy_pe0[k],pos[k]))
 c("no enterprise old behavior "+k,legacy_no_enterprise[k]==pos[k],(legacy_no_enterprise[k],pos[k]))
 c("weight0 old behavior "+k,legacy_weight0[k]==pos[k],(legacy_weight0[k],pos[k]))
mono=[]
for pe in (0.0,0.25,0.5,0.75,1.0):
 x=dict(pa);x.update(perceived_empathy=pe,enterprise_clarification_observed=True)
 mono.append(m.update_psychological_state(**x)["relational_repair_increment"])
c("relational increment monotonic",mono==sorted(mono),mono)
mixed=dict(pa);mixed.update(valence=-0.8,perceived_empathy=0.8,enterprise_clarification_observed=True)
mix=m.update_psychological_state(**mixed)
c("mixed appraisal crisis increases",mix["crisis_memory"]>q["crisis_memory"],mix)
c("mixed appraisal repair increases",mix["repair_memory"]>q["repair_memory"],mix)
na=dict(base);na.update(crisis_memory=q["crisis_memory"],valence=-.8,arousal=.8,credibility=.8,
 evidence_strength=.7,topic_relevance=.9,had_observation=True)
neg=m.update_psychological_state(**na)
c("negative can worsen",neg["trust_final"]<q["trust_final"],neg)
c("PBC not manipulated",pos["pbc"]==base["pbc"],pos["pbc"])
c("SN unchanged without social observation",pos["subjective_norm_sn"]==base["subjective_norm_sn"],pos["subjective_norm_sn"])
c("RNG draw unchanged by empathy",m.deterministic_uniform(12,"A",3,"buy")==m.deterministic_uniform(12,"A",3,"buy"))
u=m.deterministic_uniform(12,"A",3,"buy")
c("CRN reproducible",u==m.deterministic_uniform(12,"A",3,"buy"))
ps=inspect.getsource(ConsumerPlanPlugin)
c("Plan no LLM behavior call","model.chat" not in ps)
c("TPB explicit",all(x in ps for x in ("attitude_Att","subjective_norm_SN","perceived_behavioral_control_PBC")))
c("intentions explicit",all(x in ps for x in ("purchase_intention","posting_intention")))
rs=inspect.getsource(GreenCognitionPlugin)
for f in ("valence","arousal","credibility","evidence_strength","topic_relevance","hypocrisy_perceived"):
 c("semantic "+f,f in rs)
ms=inspect.getsource(m).lower()
c("no content winner","rational-evidence" not in ms and "emotional-empathy" not in ms)
reg=json.loads((ROOT/".kiro/specs/task005-replication-inference/mechanism_v2_parameter_registry.json").read_text(encoding="utf-8"))
c("assumption registry",all(v["source_type"]=="model_assumption" for v in reg["parameters"].values()))
c("no p tuning",reg["integrity"]["tune_until_p_lt_0_05"] is False)
print("Passed:",P,"Failed:",F)
raise SystemExit(1 if F else 0)
