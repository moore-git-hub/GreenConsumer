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
na=dict(base);na.update(crisis_memory=q["crisis_memory"],valence=-.8,arousal=.8,credibility=.8,
 evidence_strength=.7,topic_relevance=.9,had_observation=True)
neg=m.update_psychological_state(**na)
c("negative can worsen",neg["trust_final"]<q["trust_final"],neg)
c("PBC not manipulated",pos["pbc"]==base["pbc"],pos["pbc"])
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
