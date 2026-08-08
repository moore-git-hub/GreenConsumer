# Mechanism-v2 TPB/memory/intention/seeded-behavior layer.
from __future__ import annotations
from agentkernel_standalone.mas.agent.base.plugin_base import PlanPlugin
from mechanism_v2 import SCHEMA,MEMORY_RETENTION,behavior_probabilities,deterministic_uniform,update_psychological_state

class ConsumerPlanPlugin(PlanPlugin):
    async def init(self):pass
    def _get_agent(self):
        if hasattr(self,"agent") and self.agent:return self.agent
        if self.component and hasattr(self.component,"agent"):return self.component.agent
        if hasattr(self,"_component") and self._component:return self._component.agent
        return None
    def _get_plugin(self,name):
        a=self._get_agent()
        if not a:return None
        c=a.get_component(name)
        return getattr(c,"_plugin",getattr(c,"plugin",None)) if c else None
    async def execute(self,current_tick:int)->None:
        a=self._get_agent()
        if not a:return
        st=self._get_plugin("state"); prof=self._get_plugin("profile")
        if not st or not prof:return
        sd=getattr(st,"state_data",getattr(st,"_state_data",{}))
        obs=sd.get("last_observations") or []; had=bool(obs)
        has_clr=any(isinstance(o,dict) and (o.get("source")=="Enterprise_Clarification" or o.get("type")=="clarification") for o in obs)
        clr_type=""
        for o in obs:
            if isinstance(o,dict) and (o.get("source")=="Enterprise_Clarification" or o.get("type")=="clarification"):
                clr_type=str(o.get("content_factor","unknown"));break
        quiet=int(sd.get("quiet_ticks",0));quiet=quiet+1 if not had else 0
        prev=float(sd.get("trust_score",5));base=float(sd.get("baseline_trust",prev))
        state=update_psychological_state(
          baseline_trust=base,previous_trust=prev,
          attitude_att=float(sd.get("attitude_Att",max(0,min(1,base/10)))),
          subjective_norm_sn=float(sd.get("subjective_norm_SN",.5)),
          pbc=float(sd.get("perceived_behavioral_control_PBC",.5)),
          crisis_memory=float(sd.get("crisis_memory",0)),repair_memory=float(sd.get("repair_memory",0)),
          valence=float(sd.get("semantic_valence",0)),arousal=float(sd.get("semantic_arousal",0)),
          credibility=float(sd.get("semantic_credibility",.5)),
          evidence_strength=float(sd.get("semantic_evidence_strength",0)),
          topic_relevance=float(sd.get("semantic_topic_relevance",0)),had_observation=had,
          social_observation_count=int(sd.get("semantic_social_observation_count",0)))
        last=sd.get("last_post_tick",None)
        since=None if last in (None,"") else current_tick-int(last)
        bp,pp=behavior_probabilities(purchase_intention=state["purchase_intention"],
          posting_intention=state["posting_intention"],had_observation=had,
          already_purchased=bool(sd.get("ever_purchased",False)),ticks_since_last_post=since)
        seed=int(sd.get("behavior_seed_base",0))
        bd=deterministic_uniform(seed,a.agent_id,current_tick,"buy")
        pd=deterministic_uniform(seed,a.agent_id,current_tick,"post")
        buying=bd<bp;posting=pd<pp
        thought=sd.get("latest_thought") or {};reason=str(thought.get("reasoning","")).strip()
        post=reason if posting and reason else ("I am still evaluating this brand." if posting else "")
        if buying:await st.set_state("ever_purchased",True)
        if posting:await st.set_state("last_post_tick",current_tick)
        final=float(state["trust_final"]);anchor=float(sd.get("shock_anchor",prev))
        after=final if had else anchor
        for k,x in {"quiet_ticks":quiet,"trust_score":final,"shock_anchor":after,
          "attitude_Att":state["attitude_att"],"subjective_norm_SN":state["subjective_norm_sn"],
          "perceived_behavioral_control_PBC":state["pbc"],"emotion_valence":state["emotion_valence"],
          "emotion_arousal":state["emotion_arousal"],"crisis_memory":state["crisis_memory"],
          "repair_memory":state["repair_memory"],"purchase_intention":state["purchase_intention"],
          "posting_intention":state["posting_intention"]}.items():await st.set_state(k,x)
        gap=base-anchor;lift=after-anchor if has_clr else "";ratio=((lift/gap) if abs(gap)>1e-12 else 0.0) if has_clr else ""
        plan={"mechanism_schema_version":SCHEMA,"current_trust":final,"is_buying":buying,"is_posting":posting,
          "post_content":post,"reason":f"TPB-v2 I={state['purchase_intention']:.3f} Trust={final:.3f}",
          "trust_after_decay":state["trust_before_signal"],"affective_change":state["affective_change"],
          "shock_anchor":anchor,"decay_lambda":1-MEMORY_RETENTION,"quiet_ticks":quiet,
          "previous_trust_raw":prev,"baseline_trust_raw":base,
          "trust_after_decay_raw":state["trust_before_signal"],"affective_change_raw":state["affective_change"],
          "trust_score_raw":final,"shock_anchor_before_raw":anchor,"shock_anchor_after_raw":after,
          "decay_rate_raw":1-MEMORY_RETENTION,"sensitivity_multiplier":1.0,
          "trust_clipped_at_bound":final<=0 or final>=10,
          "anchor_update_branch":"mechanism_v2_clarification" if has_clr else ("mechanism_v2_observation" if had else "mechanism_v2_quiet"),
          "clr_anchor_lift_ratio":ratio,"clr_lift_raw":lift,"is_quiet_day":not had,
          "clarification_detected_by_plan":has_clr,"clarification_content_type":clr_type,
          "plan_fallback_used":False,"attitude_att":state["attitude_att"],
          "subjective_norm_sn":state["subjective_norm_sn"],"pbc":state["pbc"],
          "emotion_valence":state["emotion_valence"],"emotion_arousal":state["emotion_arousal"],
          "crisis_memory_before":state["crisis_memory_before"],"repair_memory_before":state["repair_memory_before"],
          "crisis_memory":state["crisis_memory"],"repair_memory":state["repair_memory"],
          "purchase_intention":state["purchase_intention"],"posting_intention":state["posting_intention"],
          "buy_probability":bp,"post_probability":pp,"buy_draw":bd,"post_draw":pd,
          "semantic_valence":float(sd.get("semantic_valence",0)),
          "semantic_arousal":float(sd.get("semantic_arousal",0)),
          "semantic_credibility":float(sd.get("semantic_credibility",.5)),
          "semantic_evidence_strength":float(sd.get("semantic_evidence_strength",0)),
          "semantic_topic_relevance":float(sd.get("semantic_topic_relevance",0))}
        await st.set_state("plan_result",plan)
    async def save_to_db(self):pass
    async def load_from_db(self):pass
