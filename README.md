Very rudimentary tool for analyzing a codebase.

This assumes a model that supports tool calls -- this may be insane, but asking the
model to 'pull' context rather than guessing/pushing context in might work better.

I'm trying to use a Language Server Protocol server as a set of tools for the model
to chat with to get to a reasonable conclusion, which may also be insane but this is
something I am doing for fun, not for work.

If I knew how to do raw calls to the LSP, and which ones would make sense here, that
would let me feed the LLM some better tools.

If I understood how tree-sitter worked that would give me a pretty cool polyglot
thing here.

# Create Virtualenv/Pull Model

```shell
pyenv virtualenv 3.12 code-assistant-intelligence
pyenv activate code-assistant-intelligence
pip install -r requirements.txt
ollama pull llama3.2:latest
```
