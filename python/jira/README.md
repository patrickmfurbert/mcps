# Jira MCP Server

A Python MCP (Model Context Protocol) server that exposes Jira Data Center as a set of tools for AI assistants. Supports browsing projects, searching and managing issues, working with sprints and boards, and managing comments — queryable through natural language via Copilot CLI or any MCP-compatible host.

## Platform

These instructions assume a Linux environment. Path references (e.g. `/home/your-username/`) and install commands are Linux-specific. Windows and macOS users will need to adjust paths and package manager commands accordingly. See the Windows Configuration section below for Windows-specific instructions.

## Tools

**Issues**
- `get_issue` — get an issue by key including summary, status, assignee, and description
- `search_issues` — search using JQL (Jira Query Language)
- `create_issue` — create a new issue
- `update_issue` — update fields on an issue (summary, description, assignee, priority)
- `get_issue_transitions` — get available transitions for an issue
- `transition_issue` — move an issue to a new status using a transition ID
- `assign_issue` — assign an issue to a user
- `get_comments` — get all comments on an issue
- `add_comment` — add a comment to an issue

**Projects**
- `list_projects` — list all accessible projects
- `get_project` — get details of a specific project

**Boards and Sprints**
- `list_boards` — list boards, optionally filtered by project
- `get_active_sprint` — get the active sprint for a board
- `get_sprint_issues` — get all issues in a sprint

**Users**
- `get_current_user` — get the currently authenticated user
- `search_users` — search for users by display name or username

## How Jira Transitions Work

Jira issue statuses are changed via transitions, not by setting the status directly. Each transition has an ID that varies per project workflow. Always call `get_issue_transitions` first to retrieve the available transitions and their IDs, then call `transition_issue` with the correct ID. Copilot will handle this automatically if you ask naturally — for example "move PROJ-123 to In Progress."

## Jira Data Center APIs

This server uses two Jira REST APIs:

- **Core API** (`/rest/api/2`) — issues, projects, users, comments
- **Agile API** (`/rest/agile/1.0`) — boards, sprints

Both are accessed using the same credentials. The server handles routing between them automatically.

## Prerequisites

### Python
```bash
