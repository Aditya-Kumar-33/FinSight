from federator import run_federated_query
from integrator import integrate


def execute_query(nl_query: str):
    plan, df_price, df_fund = run_federated_query(nl_query)
    results, llm_summary = integrate(plan, df_price, df_fund, nl_query)
    return plan, results, llm_summary
