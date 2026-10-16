from agents.planner import planner_agent
from agents.checker import checker_agent
from agents.retriever import search_policies
from agents.llm import ask_llm


def replanner_agent(conn, origin_name, dest_name, mbta_key, max_tries=3):
    # 1. Plan and check the normal route
    plan = planner_agent(conn, origin_name, dest_name)
    if not plan["ok"]:
        return {"ok": False, "reason": plan["reason"]}

    check = checker_agent(plan, mbta_key)
    if check["safe"]:
        return {"ok": True, "changed": False, "plan": plan,
                "explanation": "Your route is clear. No accessibility outages affect your trip."}

    problems = check["blocking"]

    # 2. Try to reroute around blocked stations, re-checking each new route
    avoid, new_plan, found = [], None, False
    for _ in range(max_tries):
        avoid += [p["station_id"] for p in check["blocking"]]
        new_plan = planner_agent(conn, origin_name, dest_name, avoid=avoid)
        if not new_plan["ok"]:
            break
        check = checker_agent(new_plan, mbta_key)
        if check["safe"]:
            found = True
            break

    # 3. Retrieve relevant MBTA policy
    query = "wheelchair accessible alternative when elevator is out: " + \
            "; ".join(p["alert"] for p in problems)
    policies = search_policies(conn, query, k=4)

    # 4. Ask the LLM for a grounded explanation
    problems_text = "\n".join(f"- {p['station']} ({p['role']}): {p['alert']}" for p in problems)
    route_text = " → ".join(new_plan["stations"]) if found else "No fully step-free train route found."
    policy_text = "\n\n".join(f"[{p['source']}] {p['chunk']}" for p in policies)

    prompt = f"""You are TransitWise, helping an MBTA rider who needs step-free access.

ORIGINAL ROUTE: {" → ".join(plan["stations"])}

ACCESSIBILITY PROBLEMS ON THAT ROUTE:
{problems_text}

ALTERNATIVE ROUTE (computed by our planner): {route_text}

MBTA POLICY EXCERPTS:
{policy_text}

Instructions:
- Explain the problem and the recommended option in plain language, under 150 words.
- Only recommend the alternative route above, or options explicitly stated in the policy excerpts or alerts.
- Cite the source file in [brackets] for every policy claim.
- If nothing supports a safe option, say so and suggest contacting the MBTA.
"""

    return {
        "ok": True,
        "changed": True,
        "original_plan": plan,
        "problems": problems,
        "new_plan": new_plan if found else None,
        "explanation": ask_llm(prompt),
        "sources": sorted({p["source"] for p in policies}),
    }