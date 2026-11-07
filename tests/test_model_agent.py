import json
from decimal import Decimal
from unittest import TestCase

from src.agents import AGENTS, Context, Headline
from src.model_agent import ModelAgent, OfflineFixture, parse_intent


class ModelTests(TestCase):
    def setUp(self):
        self.context = Context(1, Decimal(1), Decimal(1), Decimal(1), (),
                               (Headline("N01","示例","公开数据",100),),
                               (("RISK","120"),("sUSD","160")), 18, 30, 5)
        self.spec = dict(model="fixture-v1",max_calls=1,max_tokens=100,timeout_seconds=2,max_cost_usd=0,temperature=0)
        self.answer = json.loads(OfflineFixture().decide({})["decision"])

    def test_schema_rejects_extra_fields_future_ids_and_duplicate_keys(self):
        for decision in (dict(self.answer, reasoning="hidden"),dict(self.answer,cited_news_ids=["N02"]),
                         dict(self.answer,amount_raw="10"),dict(self.answer,confidence=True)):
            with self.assertRaises(ValueError):
                parse_intent(json.dumps(decision),self.context)
        with self.assertRaisesRegex(ValueError,"duplicate"):
            parse_intent('{"action":"hold","action":"buy"}',self.context)

    def test_only_own_wallet_and_visible_input_and_role_budget_isolation(self):
        requests = []

        class Relay(OfflineFixture):
            def decide(self, request):
                requests.append(request)
                return super().decide(request)

        first = ModelAgent(AGENTS[0],self.spec,Relay(),"fixture")
        other = ModelAgent(AGENTS[1],self.spec,Relay(),"fixture")
        self.assertEqual(first.decide(self.context).action,"hold")
        self.assertEqual(first.last_record["decision_mode"],"fixture")
        self.assertEqual(first.last_record["usage"]["calls"],0)
        first.decide(self.context)
        self.assertEqual(first.last_record["failure"],"budget_exhausted")
        other.decide(self.context)
        self.assertEqual(len(requests),2)
        self.assertEqual([r["role"] for r in requests],["trend","event"])
        snap = requests[0]["snapshot"]
        self.assertEqual(snap["own_wallet"],self.context.own_wallet)
        self.assertEqual([r["news_id"] for r in snap["visible_news"]],["N01"])
        self.assertNotIn("background_draw",snap)

    def test_timeout_has_rule_fallback_and_never_retries_unknown_bill(self):
        class Relay(OfflineFixture):
            def decide(self, _):
                raise TimeoutError()

        agent = ModelAgent(AGENTS[0],dict(self.spec,max_calls=10),Relay(),"live")
        agent.decide(self.context)
        self.assertTrue(agent.last_record["billing_uncertain"])
        self.assertEqual(agent.last_record["actual_model"],"mock-v1")
        self.assertEqual(agent.last_record["usage"]["calls"],1)
        agent.decide(self.context)
        self.assertEqual(agent.last_record["usage"]["calls"],0)
        self.assertEqual(agent.calls,1)

    def test_malformed_relay_http_does_not_stop_market(self):
        from http.client import BadStatusLine, IncompleteRead

        class BrokenDiscovery(OfflineFixture):
            def models(self):
                raise BadStatusLine("bad response")

        class BrokenDecision(OfflineFixture):
            def decide(self, _):
                raise IncompleteRead(b"{}")

        for relay in (BrokenDiscovery(), BrokenDecision()):
            agent = ModelAgent(AGENTS[0],self.spec,relay,"live")
            agent.decide(self.context)
            self.assertEqual(agent.last_record["actual_model"],"mock-v1")
