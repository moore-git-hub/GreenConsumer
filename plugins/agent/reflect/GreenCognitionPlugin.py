# Mechanism-v2 semantic appraisal layer.
from __future__ import annotations
import ast,json,re
from agentkernel_standalone.mas.agent.base.plugin_base import ReflectPlugin
from mechanism_v2 import clip,clip01,semantic_to_affective

class GreenCognitionPlugin(ReflectPlugin):
    async def init(self): pass
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
    @staticmethod
    def _parse(response):
        if isinstance(response,dict):return dict(response)
        if isinstance(response,list):
            if not response:raise ValueError("empty response")
            return GreenCognitionPlugin._parse(response[0])
        if not isinstance(response,str):raise ValueError("unsupported response")
        s=re.sub(r"```(?:json)?","",response).replace("```","").strip()
        m=re.search(r"\{.*\}",s,re.S)
        if not m:raise ValueError("no JSON")
        try:return json.loads(m.group(0))
        except Exception:
            x=ast.literal_eval(m.group(0))
            if not isinstance(x,dict):raise ValueError("not dict")
            return x
    async def execute(self,current_tick:int)->None:
        a=self._get_agent()
        if not a:return
        st=self._get_plugin("state"); prof=self._get_plugin("profile")
        if not st or not prof:return
        sd=getattr(st,"state_data",getattr(st,"_state_data",{}))
        obs=sd.get("observations") or []
        if not obs:
            vals={"semantic_valence":0.0,"semantic_arousal":0.0,"semantic_credibility":0.5,
              "semantic_evidence_strength":0.0,"semantic_topic_relevance":0.0,
              "semantic_hypocrisy_perceived":False,"semantic_observation_present":False,
              "semantic_social_observation_count":0,"raw_affective_output":0.0,
              "trust_change_affective":0.0,"affective_was_clipped":False,
              "latest_thought":None,"last_observations":[],"reflect_primary_source":"None",
              "reflect_message_sources":[]}
            for k,v in vals.items():await st.set_state(k,v)
            return
        glob=[o for o in obs if o.get("source")=="Global News"]
        clr=[o for o in obs if o.get("source")=="Enterprise_Clarification"]
        soc=[o for o in obs if o.get("source") in ("Social","social_review")]
        parts=[]; primary="Unknown"
        if glob:primary="Global News";parts.append(f"[Breaking News] {glob[0].get('content','')}")
        if clr:
            if not glob:primary="Enterprise_Clarification"
            parts.append(f"[Brand Statement] {clr[0].get('content','')}")
        if soc:
            for o in soc[:2]:parts.append(f"[Social Feed] {str(o.get('content',''))[:180]}")
            if not glob and not clr:primary="Social"
        if not parts:
            parts=[str(obs[0].get("content",""))];primary=str(obs[0].get("source","Unknown"))
        info="\n".join(parts)
        pd=getattr(prof,"profile_data",getattr(prof,"_profile_data",{}))
        persona=pd.get("persona","You are a consumer.")
        mem=st.retrieve_memory(current_tick,info,top_k=3)
        prompt=f"""
[Character Persona]
{persona}
[Past Experiences]
{chr(10).join('- '+str(x) for x in mem) if mem else 'None'}
[Information]
Source: {primary}
{info}
Return JSON only. Do NOT decide buying or posting:
{{
 "valence": <float -1 to 1>,
 "arousal": <float 0 to 1>,
 "credibility": <float 0 to 1>,
 "evidence_strength": <float 0 to 1>,
 "topic_relevance": <float 0 to 1>,
 "hypocrisy_perceived": <boolean>,
 "importance": <float 1 to 10>,
 "reasoning": "<one concise first-person sentence in English>"
}}
A brand statement may help, do nothing, or backfire. Judge the actual content.
"""
        try:
            model=getattr(a,"model",getattr(a,"_model",None))
            if not model:raise RuntimeError("model missing")
            r=self._parse(await model.chat(prompt))
            v=clip(float(r.get("valence",0)),-1,1); ar=clip01(r.get("arousal",0))
            cr=clip01(r.get("credibility",.5)); ev=clip01(r.get("evidence_strength",0))
            tr=clip01(r.get("topic_relevance",r.get("topic_consistency",.5)))
            hyp=bool(r.get("hypocrisy_perceived",False)); imp=clip(r.get("importance",5),1,10)
            reason=str(r.get("reasoning","")).strip(); aff=semantic_to_affective(v,ar,cr)
            thought={"valence":v,"arousal":ar,"credibility":cr,"evidence_strength":ev,
              "topic_relevance":tr,"hypocrisy_perceived":hyp,"importance":imp,
              "reasoning":reason,"trust_change_affective":aff}
            vals={"semantic_valence":v,"semantic_arousal":ar,"semantic_credibility":cr,
              "semantic_evidence_strength":ev,"semantic_topic_relevance":tr,
              "semantic_hypocrisy_perceived":hyp,"semantic_observation_present":True,
              "semantic_social_observation_count":len(soc),"raw_affective_output":aff,
              "trust_change_affective":aff,"affective_was_clipped":False,
              "latest_thought":thought,"reflect_primary_source":primary,
              "reflect_message_sources":sorted({str(o.get("source","Unknown")) for o in obs}),
              "last_observations":list(obs),"observations":[]}
            for k,x in vals.items():await st.set_state(k,x)
            st.add_to_memory(current_tick,f"[Tick {current_tick}] {primary} V={v:+.2f} C={cr:.2f} E={ev:.2f} | {reason}",imp)
        except Exception as e:
            print(f"[Reflect-v2 ERROR] {a.agent_id}: {type(e).__name__}: {e}")
            vals={"semantic_valence":0.0,"semantic_arousal":0.0,"semantic_credibility":0.5,
              "semantic_evidence_strength":0.0,"semantic_topic_relevance":0.0,
              "semantic_hypocrisy_perceived":False,"semantic_observation_present":True,
              "semantic_social_observation_count":len(soc),"raw_affective_output":0.0,
              "trust_change_affective":0.0,"affective_was_clipped":False,
              "latest_thought":{"valence":0.0,"arousal":0.0,"credibility":0.5,
                "evidence_strength":0.0,"topic_relevance":0.0,"hypocrisy_perceived":False,
                "importance":0.0,"reasoning":"","semantic_fallback_used":True},
              "reflect_primary_source":primary,
              "reflect_message_sources":sorted({str(o.get("source","Unknown")) for o in obs}),
              "last_observations":list(obs),"observations":[]}
            for k,x in vals.items():await st.set_state(k,x)
    async def save_to_db(self):pass
    async def load_from_db(self):pass
