# TASK_005 mechanism v2 core.
# All numeric defaults are model assumptions and must be sensitivity-tested.
# No treatment identity is used in the transition equations.
from __future__ import annotations
import hashlib, math

SCHEMA="2.0"
MEMORY_RETENTION=0.97
ATTITUDE_UPDATE_RATE=0.25
SUBJECTIVE_NORM_UPDATE_RATE=0.20
TRUST_CRISIS_WEIGHT=1.0
TRUST_REPAIR_WEIGHT=1.0
PURCHASE_OPPORTUNITY_RATE=0.10
POSTING_OPPORTUNITY_RATE=0.45
POSTING_COOLDOWN_TICKS=2

def clip(x,lo,hi): return max(lo,min(hi,float(x)))
def clip01(x): return clip(x,0.0,1.0)
def sigmoid(x):
    x=clip(x,-60,60)
    return 1/(1+math.exp(-x))

def semantic_to_affective(valence,arousal,credibility):
    v=clip(valence,-1,1); a=clip01(arousal); c=clip01(credibility)
    mag=abs(v)*(0.5+0.5*a)*(0.5+0.5*c)
    return -2.0*mag if v<0 else 1.5*mag

def deterministic_uniform(seed,agent_id,tick,action):
    b=f"{int(seed)}|{agent_id}|{int(tick)}|{action}".encode()
    n=int.from_bytes(hashlib.sha256(b).digest()[:8],"big")
    return n/float(2**64)

def update_psychological_state(*,baseline_trust,previous_trust,attitude_att,
    subjective_norm_sn,pbc,crisis_memory,repair_memory,valence,arousal,
    credibility,evidence_strength,topic_relevance,had_observation,
    social_observation_count):
    base=clip(baseline_trust,0,10); prev=clip(previous_trust,0,10)
    att=clip01(attitude_att); sn=clip01(subjective_norm_sn); pbc=clip01(pbc)
    cb=max(0,float(crisis_memory))*MEMORY_RETENTION
    rb=max(0,float(repair_memory))*MEMORY_RETENTION
    before=clip(base+TRUST_REPAIR_WEIGHT*rb-TRUST_CRISIS_WEIGHT*cb,0,10)
    v=clip(valence,-1,1); a=clip01(arousal); c=clip01(credibility)
    e=clip01(evidence_strength); r=clip01(topic_relevance)
    ca,ra=cb,rb; affect=0.0
    if had_observation:
        affect=semantic_to_affective(v,a,c)
        iw=(0.5+0.5*c)*(0.5+0.5*r)
        if affect<0: ca+=(-affect)*iw
        elif affect>0: ra+=affect*iw*(0.5+0.5*e)
        v01=(v+1)/2
        signal=clip01(0.45*v01+0.25*c+0.20*e+0.10*r)
        att=clip01((1-ATTITUDE_UPDATE_RATE)*att+ATTITUDE_UPDATE_RATE*signal)
        if int(social_observation_count)>0:
            sn=clip01((1-SUBJECTIVE_NORM_UPDATE_RATE)*sn+SUBJECTIVE_NORM_UPDATE_RATE*v01)
    trust=clip(base+TRUST_REPAIR_WEIGHT*ra-TRUST_CRISIS_WEIGHT*ca,0,10)
    z=-0.50+1.40*(att-.5)+0.80*(sn-.5)+0.60*(pbc-.5)+1.20*(trust/10-.5)
    ibuy=sigmoid(z)
    ipost=sigmoid(-1.0+1.20*a+0.80*abs(v)) if had_observation else 0.0
    return dict(trust_before_signal=before,trust_final=trust,attitude_att=att,
        subjective_norm_sn=sn,pbc=pbc,emotion_valence=v if had_observation else 0.0,
        emotion_arousal=a if had_observation else 0.0,crisis_memory_before=cb,
        repair_memory_before=rb,crisis_memory=ca,repair_memory=ra,
        affective_change=affect,purchase_intention=ibuy,posting_intention=ipost,
        trust_delta=trust-prev)

def behavior_probabilities(*,purchase_intention,posting_intention,had_observation,
    already_purchased,ticks_since_last_post):
    bp=0.0 if already_purchased else PURCHASE_OPPORTUNITY_RATE*clip01(purchase_intention)
    pp=POSTING_OPPORTUNITY_RATE*clip01(posting_intention) if had_observation else 0.0
    if ticks_since_last_post is not None and ticks_since_last_post<=POSTING_COOLDOWN_TICKS: pp=0.0
    return clip01(bp),clip01(pp)
