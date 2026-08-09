"""Category 6 (S-01..S-10) — SOTA autonomous core tests."""
import asyncio
import pytest

from agent.autopilot import AutoPilot, SafetyLimits, AutoPilotResult
from agent.swarm import swarm, AgentSpec
from agent.reflexion import ReflexionLoop
from agent.auxiliary import KnowledgeHarvester, ToTPlanner, Scheduler


@pytest.mark.asyncio
async def test_autopilot_completes_simple_goal():
    async def plan(g): return ["step-1", "step-2"]
    async def exec_ok(s): await asyncio.sleep(0); return True
    async def verify(g): await asyncio.sleep(0); return True

    class A(AutoPilot):
        pass

    ap = A(plan, exec_ok, verify)
    res = await ap.run("say hello")
    assert res.status == "completed" and res.iterations == 2 and "plan" in res.trace[0]


@pytest.mark.asyncio
async def test_autopilot_aborts_at_iteration_cap():
    async def plan(g): return ["x"] * (SafetyLimits.MAX_ITERATIONS + 5)
    async def exec_ok(s): await asyncio.sleep(0); return True
    async def verify(g): await asyncio.sleep(0); return True
    ap = AutoPilot(plan, exec_ok, verify)
    res = await ap.run("never-ending")
    assert res.status == "aborted" and res.iterations == SafetyLimits.MAX_ITERATIONS


@pytest.mark.asyncio
async def test_swarm_collects_results_and_errors():
    async def run(task):
        if task == "bad":
            raise RuntimeError("boom")
        await asyncio.sleep(0)
        return task

    agents = [AgentSpec("a", "ok1"), AgentSpec("b", "bad"), AgentSpec("c", "ok2")]
    res = await swarm(agents, run)
    assert sorted(res.results) == ["ok1", "ok2"]
    assert len(res.errors) == 1 and "boom" in res.errors[0]


@pytest.mark.asyncio
async def test_reflexion_revise_low_confidence():
    seen = {}
    async def critic(out):
        seen["called"] = True
        return out + " [revised]"

    loop = ReflexionLoop(critic)
    assert await loop.maybe_revise("draft", confidence=0.6) == "draft"
    assert await loop.maybe_revise("draft", confidence=0.2) == "draft [revised]"


@pytest.mark.asyncio
async def test_tot_planner_picks_best():
    async def gen(g): return ["bad", "best", "worse"]
    score = lambda p: 0.9 if p == "best" else 0.1
    planner = ToTPlanner(gen, score)
    plan, sc = await planner.best_plan("any")
    assert sc == 0.9 and plan == ["best"]


@pytest.mark.asyncio
async def test_scheduler_runs_job():
    called = []
    async def job(): called.append(True)
    s = Scheduler()
    s.every(0.01, job)
    await asyncio.sleep(0.05)
    await s.stop_all()
    assert called


def test_plugin_manifest_parses(tmp_path):
    p = tmp_path / "forge-plugin.toml"
    p.write_text(
        '[plugin]\nname="x"\nversion="0.1.0"\ndescription="d"\nentry="x:main"\n',
        encoding="utf-8",
    )
    import openforge.plugin_manifest as pm
    m = pm.parse_manifest(str(p))
    assert m.name == "x" and m.entry == "x:main" and m.version == "0.1.0"
