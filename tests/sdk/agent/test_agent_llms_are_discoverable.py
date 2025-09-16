from openhands.sdk import LLM, Agent, LLMSummarizingCondenser


def check_service_id_exists(service_id: str, llms: list[LLM]):
    service_ids = [llm.service_id for llm in llms]
    return service_id in service_ids


def test_automatic_llm_discovery():
    llm_service_id = "main-agent"
    agent = Agent(llm=LLM(model="test-model", service_id=llm_service_id))

    llms = list(agent.get_all_llms())
    assert len(llms) == 1
    assert check_service_id_exists(llm_service_id, llms)


def test_automatic_llm_discovery_for_multiple_llms():
    llm_service_id = "main-agent"
    condenser_service_id = "condenser"

    condenser = LLMSummarizingCondenser(
        llm=LLM(model="test-model", service_id=condenser_service_id)
    )

    agent = Agent(
        llm=LLM(model="test-model", service_id=llm_service_id), condenser=condenser
    )

    llms = list(agent.get_all_llms())
    assert len(llms) == 2
    assert check_service_id_exists(llm_service_id, llms)
    assert check_service_id_exists(condenser_service_id, llms)


def test_automatic_llm_discovery_for_custom_agent_with_duplicates():
    class CustomAgent(Agent):
        model_routers: list[LLM] = []

    llm_service_id = "main-agent"
    router_service_id = "secondary_llm"
    router_service_id_2 = "tertiary_llm"
    condenser_service_id = "condenser"

    condenser = LLMSummarizingCondenser(
        llm=LLM(model="test-model", service_id=condenser_service_id)
    )

    agent_llm = LLM(model="test-model", service_id=llm_service_id)
    router_llm = LLM(model="test-model", service_id=router_service_id)
    router_llm_2 = LLM(model="test-model", service_id=router_service_id_2)

    agent = CustomAgent(
        llm=agent_llm,
        condenser=condenser,
        model_routers=[agent_llm, router_llm, router_llm_2],
    )

    llms = list(agent.get_all_llms())
    assert len(llms) == 4
    assert check_service_id_exists(llm_service_id, llms)
    assert check_service_id_exists(router_service_id, llms)
    assert check_service_id_exists(router_service_id_2, llms)
    assert check_service_id_exists(condenser_service_id, llms)
