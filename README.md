# Introduction

Very rudimentary tool for analyzing a codebase.

Error handling? Lol. Structure? All one file, my man. This was done with some severe
time constraints.

This assumes a model that supports tool calls -- this may be insane, but asking the
model to 'pull' context rather than guessing/pushing context in might work better.

I'm trying to use a Language Server Protocol server as a set of tools for the model
to chat with to get to a reasonable conclusion, which may also be insane but this is
something I am doing for fun, not for work.

If I knew how to do raw calls to the LSP, and which ones would make sense here, that
would let me feed the LLM some better tools.

I think using a LSP gives me the ability to:

1. Utilize a large library of existing community projects to handle many languages.
2. Use the LLM for what it's good at (gluing together information in context) while
   using best-in-class static analysis tools to do what LLMs are not good at (namely,
   facts and deterministic knowledge)

If I understood how tree-sitter worked that would give me a pretty cool polyglot
thing here on the syntax of the code as well, but LSP is a better bet for now. I
just wish I knew more calls I could do on it.

## Unzip `grip-no-tests` in local dir

Unzip `grip-no-tests.zip` in this folder. Or edit all the hardcoded references to
`grip-no-tests` to the full path to another folder. It's up to you!

## Install Ollama

Go to https://ollama.com/download/ and do the thing.

## Create Virtualenv/Pull Model

```shell
pyenv virtualenv 3.12 code-assistant-intelligence
pyenv activate code-assistant-intelligence
pip install -r requirements.txt
ollama pull llama3.2:latest
```

## Run service

```shell
fastapi dev main.py
```

You can go into http://127.0.0.1:8000/docs#/default/query_repo_query_post in your
browser and type in a query. It's `curl`able too. Standard FastAPI with Pydantic.

Alternately, you can run `python main.py` directly as a command line utility:

```shell

python main.py 'What does ReadmeRenderer do?'
```
