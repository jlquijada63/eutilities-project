from __future__ import annotations

import asyncio

from agents import Agent, Runner, function_tool

from async_eutilities import efetch, esearch


@function_tool
async def search_pubmed_pmids(term: str, retmax: int = 5) -> list[str]:
    """Search PubMed and return PMIDs."""
    options = {"retmax": max(1, min(retmax, 50))}
    return await esearch(term=term, db="pubmed", options=options)


@function_tool
async def fetch_pubmed_record(pmid: str) -> dict:
    """Fetch one PubMed record by PMID and return it as a dictionary."""
    record = await efetch(pmid=pmid, db="pubmed")
    return record.model_dump()


agent = Agent(
    name="PubMed Agent",
    instructions=(
        "You are a conversational PubMed assistant. "
        "Use search_pubmed_pmids to find PMIDs and fetch_pubmed_record to retrieve record details. "
        "Ask clarifying questions when needed and keep answers concise with PMIDs when possible."
    ),
    tools=[search_pubmed_pmids, fetch_pubmed_record],
)


def _extract_text_output(run_result) -> str:
    output = getattr(run_result, "final_output", None)
    if output is None:
        try:
            output = run_result.final_output_as(str)
        except Exception:
            output = "No output generated."
    return output if isinstance(output, str) else str(output)


async def chat() -> None:
    print("PubMed conversational agent listo. Escribe 'exit' para salir.\n")

    conversation: list[dict] | str = []
    while True:
        user_message = input("You: ").strip()
        if not user_message:
            continue
        if user_message.lower() in {"exit", "quit", "salir"}:
            print("Bye.")
            break

        result = await Runner.run(agent, conversation + [{"role": "user", "content": user_message}])
        print(f"Agent: {_extract_text_output(result)}\n")
        conversation = result.to_input_list()


if __name__ == "__main__":
    asyncio.run(chat())
