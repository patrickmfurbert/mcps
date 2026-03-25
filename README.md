# mcps

A collection of [MCP (Model Context Protocol)](https://modelcontextprotocol.io) servers — small, self-contained services that expose tools to AI assistants like GitHub Copilot CLI.

## Setup

Clone into your `~/projects` directory:
```bash
git clone https://github.com/patrickmfurbert/mcps.git ~/projects/mcps
```

## Servers

| Path | Language | Description |
|------|----------|-------------|
| [`python/calculator`](python/calculator) | Python | Test MCP — basic arithmetic (`add`, `subtract`) via FastMCP |
| [`python/bitbucket`](python/bitbucket) | Python | Bitbucket Data Center — PRs, repos, branches, and build status via FastMCP |
| [`python/splunk`](python/splunk) | Python | Splunk Enterprise — SPL searches, indexes, sourcetypes, and saved searches via FastMCP |
| [`python/confluence`](python/confluence) | Python | Confluence - searches and lookups |
| [`python/jira`](python/jira) | Python | Jira Data Center — projects, issues, sprints, boards, and comments via FastMCP |
