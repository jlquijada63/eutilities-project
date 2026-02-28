import asyncio

from async_eutilities import EFetchRecord, efetch, esearch


async def main() -> list[EFetchRecord]:
    ids = await esearch(term="ankle fractures", options={"retmax": 5})
    if not ids:
        raise ValueError("No IDs found in ESearch response.")

    return [await efetch(pmid=idx) for idx in ids]


if __name__ == "__main__":
    response = asyncio.run(main())
    for item in response:
      print(item.article_title)
