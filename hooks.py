
from agents import Agent, RunHooks, TContext, RunContextWrapper, TResponseInputItem
from agents.tool import Tool
from typing import Optional



class RunPubMedHook (RunHooks):

    async def on_llm_start(
        self,
        context: RunContextWrapper[TContext],
        agent: Agent[TContext],
        system_prompt: Optional[str],
        input_items: list[TResponseInputItem],
    ) -> None:
        """Called immediately before the agent issues an LLM call."""
        print("Inicializando agente")

    async def on_tool_start(
        self,
        context: RunContextWrapper[TContext],
        agent: Agent,
        tool: Tool,
    ) -> None:
        """Called immediately before a local tool is invoked."""
        print (f"Buscando en Pubmed con {tool.name}")
