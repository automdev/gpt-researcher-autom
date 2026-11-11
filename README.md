# gpt-researcher-autom

[GPT Researcher](https://github.com/assafelovic/gpt-researcher) retriever plugin for [Autom](https://www.autom.dev).

It registers the `autom` retriever under GPT Researcher's `gpt_researcher.retrievers` entry point, so it works without any change to GPT Researcher.

## Installation

Install the plugin in the same Python environment as GPT Researcher:

```bash
pip install gpt-researcher-autom
```

Get an API key at [app.autom.dev](https://app.autom.dev), then select the retriever:

```bash
export RETRIEVER=autom
export AUTOM_API_KEY="your-api-key"
```

You can combine it with other retrievers, such as `RETRIEVER=autom,duckduckgo`.

## Configuration

- `AUTOM_API_KEY`: your Autom API key (required).
- `AUTOM_ENGINE`: google (default), bing, brave, duckduckgo or yahoo.

The retriever returns links with their title and snippet, and GPT Researcher scrapes each page (`requires_scraping = True`). The domains in `query_domains` are added to the query as `site:` filters.

On a missing key or a failed request, the retriever logs a warning and returns no results, so one failing provider does not stop a research run. The key never appears in the logs.

## Development

```bash
pip install -e ".[test]"
pytest
```

## License

MIT
