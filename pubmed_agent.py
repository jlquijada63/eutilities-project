from __future__ import annotations

import asyncio
from typing import Any

from agents import Agent, Runner, function_tool
from rich.console import Console, RenderableType
from rich.json import JSON
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from async_eutilities import efetch, esearch

from hooks import RunPubMedHook

from prompts import AGENT_INSTRUCTIONS


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
    instructions=AGENT_INSTRUCTIONS,
    tools=[search_pubmed_pmids, fetch_pubmed_record],
    
)


def _extract_output(run_result: Any) -> Any:
    output = getattr(run_result, "final_output", None)
    if output is None:
        try:
            output = run_result.final_output_as(str)
        except Exception:
            output = "No output generated."
    return output


def _looks_like_markdown(text: str) -> bool:
    markers = ("# ", "## ", "- ", "* ", "1. ", "```", "> ")
    return any(marker in text for marker in markers)


def _format_agent_output(output: Any) -> RenderableType:
    if isinstance(output, (dict, list)):
        return JSON.from_data(output, indent=2)

    text = output if isinstance(output, str) else str(output)
    text = text.strip() or "No output generated."
    if _looks_like_markdown(text):
        return Markdown(text)
    return Text(text, overflow="fold")


def _render_user_message(console: Console, text: str) -> None:
    console.print(
        Panel(
            Text(text, style="bold cyan", overflow="fold"),
            title="You",
            border_style="cyan",
            expand=True,
        )
    )


def _render_agent_response(console: Console, output: Any) -> None:
    console.print(
        Panel(
            _format_agent_output(output),
            title="PubMed Agent",
            border_style="green",
            expand=True,
        )
    )


async def chat() -> None:
    console = Console()
    console.print(
        Panel(
            "[bold]PubMed conversational agent listo[/bold]\n"
            "Escribe [cyan]exit[/cyan], [cyan]quit[/cyan] o [cyan]salir[/cyan] para terminar.",
            border_style="blue",
            title="Session",
            expand=True,
        )
    )

    conversation: list[dict] | str = []
    while True:
        user_message = input("You: ").strip()
        if not user_message:
            continue
        if user_message.lower() in {"exit", "quit", "salir"}:
            console.print(Panel("Bye.", border_style="blue", title="Session"))
            break

        _render_user_message(console, user_message)
        result = await Runner.run(agent, 
                                  conversation + [{"role": "user", "content": user_message}],
                                  hooks=RunPubMedHook())
        _render_agent_response(console, _extract_output(result))
        console.print(Rule(style="dim"))
        conversation = result.to_input_list()


if __name__ == "__main__":
    asyncio.run(chat())
