import functools
import json
import pathlib
import typing

import click
import fastapi
from ollama import Client
from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
import pydantic


PROMPT = """
You are an expert code manipulation tool.

You are in charge of understanding and optimizing a project's codebase, and have been
provided a set of tools for auditing and manipulating this project. You must use the tools
provided to the best of your ability to answer rthe user's questions precisely and in a
concise, accurate manner.

You will also be provided with a list of filenames in the project, which may give you
additional insight into the structure of the project's code repository.

You may _only_ use code that has been presented to you, either via a prompt or as a
tool call from `get_file_source`. Please use `get_file_source` as your source for truth for
code.

Once you have gotten the results from a tool call, please feel free to issue additional
tool calls to further dig into the problem.
"""


SymbolLocation = typing.TypedDict(
    "SymbolLocation", {"file_path": str, "row": int, "column": int}
)


# Functions to send to llama, so it can call them.
def compute_tools_for_context(
    local_path: pathlib.Path, lsp: SyncLanguageServer
) -> dict[str, callable]:
    """The functions in e.g. the lsp's docstrings are broken, so we're sending a wrapped
    'bare' version to the tool calls so it gets the parameter names right.
    """

    def list_files_in_repository() -> list[str]:
        """Returns a list of all the files in the code repository"""
        file_list = []
        for path, dirs, files in local_path.walk(follow_symlinks=False):
            if path.name.startswith("."):
                # Ignore dot dirs -- don't winnow down
                dirs.clear()
                continue

            for file in files:
                relative_file_name = ((local_path / path) / file).relative_to(
                    local_path
                )
                if path.name.startswith("."):
                    continue

                file_list.append(str(relative_file_name))

        return file_list

    def find_string_in_file(
        file_path: str, string_pattern: str
    ) -> list[SymbolLocation]:
        """Finds a list of rows and columns a string occurs in within a file."""
        patterns = []
        if not file_path:
            return patterns

        abs_path = local_path / file_path
        if abs_path.is_relative_to(local_path):
            with open(str(abs_path), "r") as in_handle:
                for line_number, line in enumerate(in_handle):
                    if string_pattern.lower() in line.lower():
                        patterns.append(
                            {
                                "file_path": file_path,
                                "row": line_number + 1,
                                "column": line.index(string_pattern) + 1,
                            }
                        )

        return tuple(patterns)

    def find_string_in_repository(string_pattern: str) -> list[SymbolLocation]:
        """Finds all the matching instances of a search string in the repository,
        in all files."""
        symbols = []
        for file in list_files_in_repository():
            try:
                symbols.extend(find_string_in_file(file, string_pattern))
            except:
                pass

        return tuple(symbols)

    def request_document_symbols(file_path: str) -> list[dict]:
        """Gets a list of defined code symbols in a file."""
        symbols = lsp.request_document_symbols(file_path)[0]
        # This pares down the size of the symbol dict, but doesn't seem helpful.
        for s in symbols:
            for key in ("range", "selectionRange"):
                if key in s:
                    pass  # del s[key]
        return symbols

    def request_repository_symbols() -> list[dict]:
        """Finds all code symbols defined in a repository."""
        symbols = []
        for file in list_files_in_repository():
            try:
                ds = request_document_symbols(file)
                symbols.extend(d | {"file_path": file} for d in ds)
            except:
                pass

        return tuple(symbols)

    def request_references(file_path: str, code: str):
        """Find all the references for a specific piece of code in a file."""
        return [
            lsp.request_references(file_path, pattern["row"], pattern["column"])
            for pattern in find_string_in_file(file_path, code)
        ]

    def get_file_source(file_path: str) -> str:
        if not file_path:
            return "Nothing in this file"

        try:
            abs_path = local_path / file_path
            if abs_path.is_relative_to(local_path):
                with open(abs_path, "r") as in_handle:
                    return f"The contents of {file_path} are as following:\n```\n{in_handle.read()}\n```"
        except:
            pass

        return f"Cannot get contents of {file_path}"

    return {
        # functools.cache to implicitly memoize all function calls
        f.__name__: functools.cache(f)
        for f in [
            list_files_in_repository,
            find_string_in_file,
            find_string_in_repository,
            request_document_symbols,
            request_repository_symbols,
            request_references,
            get_file_source,
        ]
    }


# Interesting part
def query_repo_for_information(prompt: str, path: str = "."):
    localpath = pathlib.Path(path).absolute()

    config = MultilspyConfig.from_dict({"code_language": "python"})
    logger = MultilspyLogger()
    lsp = SyncLanguageServer.create(config, logger, str(localpath))
    with lsp.start_server():
        tool_dict = compute_tools_for_context(localpath, lsp)

        messages = [
            {"role": "system", "content": PROMPT},
            {
                "role": "assistant",
                "content": f"Here are the names of all the files in the project:\n```\n{'\n'.join(tool_dict['list_files_in_repository']())}\n```",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]

        made_tool_calls_in_this_loop = True

        loops = 0

        while made_tool_calls_in_this_loop and loops < 10:
            response = Client().chat(
                model="llama3.2:latest",
                tools=tool_dict.values(),
                messages=messages,
            )
            made_tool_calls_in_this_loop = False

            for tool in response.message.tool_calls or []:
                try:
                    tool_func = tool_dict.get(tool.function.name)
                    tool_return_value = tool_func(**tool.function.arguments)
                    print(
                        f"Tool call: {tool.function.name}({tool.function.arguments}) -> {tool_return_value}"
                    )
                    messages.append(
                        {"role": "tool", "content": json.dumps(tool_return_value)}
                    )
                except Exception as e:
                    print(
                        f"Tool call: {tool.function.name}({tool.function.arguments}) failed: {e}"
                    )
                    pass
                made_tool_calls_in_this_loop = True

            loops += 1

        return response.message.content


class RepositoryQuery(pydantic.BaseModel):
    question: str


class RepositoryAnswer(pydantic.BaseModel):
    response: str


app = fastapi.FastAPI()


@app.post("/query")
def query_repo(request: RepositoryQuery) -> RepositoryAnswer:
    return RepositoryAnswer(
        response=query_repo_for_information(
            prompt=request.question, path="./grip-no-tests"
        )
    )


if __name__ == "__main__":

    @click.command()
    @click.argument("query")
    def main(query):
        return_value = query_repo_for_information(
            query,
            path="./grip-no-tests",
        )

        print(" -> ", return_value)

    main()
