# 🧑‍💻 Development

[![PyPI - Version](https://img.shields.io/pypi/v/openroute-mcp.svg?logo=pypi&label=PyPI&logoColor=silver)](https://pypi.org/project/openroute-mcp/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/openroute-mcp.svg?logo=python&label=Python&logoColor=silver)](https://pypi.org/project/openroute-mcp/)
[![Tests](https://github.com/vemonet/openroute-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/vemonet/openroute-mcp/actions/workflows/test.yml)

</div>

This section is for if you want to run the package and reusable components in development, and get involved by making a code contribution.

> Requirements: [`uv`](https://docs.astral.sh/uv/getting-started/installation/) to easily handle scripts and virtual environments

## 📥️ Setup

Clone the repository:

```bash
git clone https://github.com/vemonet/openroute-mcp
cd openroute-mcp
```

Install pre-commit hooks:

```sh
uv run pre-commit install
```

**Login to [openrouteservice.org](https://openrouteservice.org/)** with GitHub, get an API key, and create a `.env` file:

```sh
echo "OPENROUTESERVICE_API_KEY=YOUR_API_KEY" > .env
```

> [!IMPORTANT]
>
> Quotas for OpenRouteService API:
>
> | API endpoint | Quota per minute | Quota per day |
> | ------------ | ---------------- | ------------- |
> | Directions   | 40               | 2000          |
> | Geocodes     | 100              | 1000          |

## ⚡️ Run the server

You can run the server using **streamable HTTP** transport in development:

```sh
uv run --env-file .env openroute-mcp --http
```

Or with **STDIO** transport:

```sh
uv run --env-file .env openroute-mcp
```

🫆 Start the **MCP inspector**:

```sh
uv run --env-file .env mcp dev src/openroute_mcp/server.py
```

**🔌 Connect a client** to the MCP server (cf. `README.md` for more details), the VSCode `mcp.json` should look like below, you will need to change the `cwd` field to provide the path to this repository on your machine:

```json
{
   "servers": {
      "openroute-mcp": {
         "type": "stdio",
         "cwd": "~/dev/openroute-mcp",
         "env": {
            "OPENROUTESERVICE_API_KEY": "YOUR_API_KEY"
         },
         "command": "uv",
         "args": [
            "run",
            "openroute-mcp"
         ]
      },
      "openroute-mcp-http": {
         "url": "http://localhost:8888/mcp",
         "type": "http"
      },
   }
}
```

## ✅ Run tests

Make sure the existing tests still work by running the test suite and linting checks. Note that any pull requests to the fairworkflows repository on github will automatically trigger running of the test suite;

```bash
uv run --env-file .env pytest
```

To display all logs when debugging:

```bash
uv run --env-file .env pytest -s
```

## 🧹 Format code

```bash
uvx ruff format
uvx ruff check --fix
```

## ♻️ Reset the environment

Upgrade `uv`:

```sh
uv self update
```

Clean `uv` cache:

```sh
uv cache clean
```

## 🏷️ Release process

> [!IMPORTANT]
>
> Get a PyPI API token at [pypi.org/manage/account](https://pypi.org/manage/account).

Run the release script providing the version bump: `fix`, `minor`, or `major`

```sh
.github/release.sh fix
```
