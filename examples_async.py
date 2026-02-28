import asyncio
import os

from eutilities import EUtilitiesClient


async def example_search_summary_fetch() -> None:
    async with EUtilitiesClient(
        api_key=os.getenv("NCBI_API_KEY"),
        email=os.getenv("NCBI_EMAIL"),
        tool="eutilities-project",
    ) as client:
        search_xml = await client.esearch(
            db="pubmed",
            term="(asthma[Title/Abstract]) AND (2024[pdat])",
            retmax=5,
            usehistory=True,
            retmode="xml",
        )
        print("=== ESearch (primeros 800 chars) ===")
        print(search_xml[:800], "\n")

        summary_xml = await client.esummary(
            db="pubmed",
            query_key=1,
            webenv=_extract_between(search_xml, "<WebEnv>", "</WebEnv>"),
            retmax=5,
            retmode="xml",
        )
        print("=== ESummary (primeros 800 chars) ===")
        print(summary_xml[:800], "\n")

        fetch_xml = await client.efetch(
            db="pubmed",
            query_key=1,
            webenv=_extract_between(search_xml, "<WebEnv>", "</WebEnv>"),
            rettype="abstract",
            retmode="xml",
            retmax=3,
        )
        print("=== EFetch (primeros 800 chars) ===")
        print(fetch_xml[:800], "\n")


async def example_spell_and_global_count() -> None:
    async with EUtilitiesClient(api_key=os.getenv("NCBI_API_KEY")) as client:
        spell_xml = await client.espell(term="diabtes mellitus", db="pubmed")
        print("=== ESpell ===")
        print(spell_xml[:500], "\n")

        gquery_xml = await client.egquery(term="diabetes mellitus")
        print("=== EGQuery ===")
        print(gquery_xml[:500], "\n")


async def example_citation_match() -> None:
    async with EUtilitiesClient(api_key=os.getenv("NCBI_API_KEY")) as client:
        bdata = "proc natl acad sci u s a|1991|88|7|3248|mann bj|"
        result = await client.ecitmatch(bdata=bdata)
        print("=== ECitMatch ===")
        print(result[:500], "\n")


def _extract_between(text: str, start: str, end: str) -> str | None:
    i = text.find(start)
    if i == -1:
        return None
    j = text.find(end, i + len(start))
    if j == -1:
        return None
    return text[i + len(start) : j]


async def main() -> None:
    await example_search_summary_fetch()
    await example_spell_and_global_count()
    await example_citation_match()


if __name__ == "__main__":
    asyncio.run(main())
