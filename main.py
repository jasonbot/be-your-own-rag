import json
import pathlib
import typing

from ollama import Client
from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger


PROMPT = """
You are an expert code manipulation tool.

You are in charge of optimizing a project's codebase, and have been provided a set of tools for
auditing and manipulating this project. You must use the tools provided to the best of your 
ability to meet the user's needs.
"""


SymbolLocation = typing.TypedDict(
    "SymbolLocation", {"file_path": str, "row": int, "column": int}
)


def compute_tools_for_context(
    local_path: pathlib.Path, lsp: SyncLanguageServer
) -> dict[str, callable]:
    def list_files() -> list[str]:
        """Returns a list of all the files in the code repository"""
        file_list = []
        for path, dirs, files in local_path.walk(follow_symlinks=False):
            if path.name.startswith("."):
                # Ignore dot dirs
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

    def find_in_file(file_path: str, string_pattern: str) -> list[SymbolLocation]:
        """Finds a list of rows and columns a string occurs in within a file."""
        patterns = []
        if not file_path:
            return patterns

        abs_path = local_path / file_path
        if abs_path.is_relative_to(local_path):
            with open(str(abs_path), "r") as in_handle:
                for line_number, line in enumerate(in_handle):
                    if string_pattern in line:
                        patterns.append(
                            {
                                "file_path": file_path,
                                "row": line_number + 1,
                                "column": line.index(string_pattern) + 1,
                            }
                        )

        return patterns

    def find_in_repository(string_pattern: str) -> list[SymbolLocation]:
        symbols = []
        for file in list_files():
            try:
                symbols.extend(find_in_file(file, string_pattern))
            except:
                pass
        return symbols

    def request_document_symbols(file_path: str) -> list[dict]:
        """Gets a list of defined symbols in a file."""
        return lsp.request_document_symbols(file_path)[0]

    def request_repository_symbols() -> list[dict]:
        """Finds all symbols defined in a repository."""
        symbols = []
        for file in list_files():
            try:
                ds = request_document_symbols(file)
                symbols.extend(d | {"file_path": file} for d in ds)
            except Exception as e:
                pass
        print("SYMNOL", symbols)
        return symbols

    def request_references(file_path: str, line: int, column: int):
        return lsp.request_references(file_path, line, column)

    def get_file_source(file_path: str) -> str:
        patterns = []
        if not file_path:
            return patterns

        abs_path = local_path / file_path
        if abs_path.is_relative_to(local_path):
            with open(abs_path, "r") as in_handle:
                return in_handle.read()

    return {
        f.__name__: f
        for f in [
            list_files,
            find_in_file,
            find_in_repository,
            request_document_symbols,
            request_repository_symbols,
            request_references,
            get_file_source,
        ]
    }


def rudimentary_chat(prompt: str, path: str = "."):
    localpath = pathlib.Path(path).absolute()

    config = MultilspyConfig.from_dict({"code_language": "python"})
    logger = MultilspyLogger()
    lsp = SyncLanguageServer.create(config, logger, str(localpath))
    messages = [
        {"role": "system", "content": PROMPT},
        {
            "role": "user",
            "content": prompt,
        },
    ]
    with lsp.start_server():
        tool_dict = compute_tools_for_context(localpath, lsp)

        tool_calls = True

        while tool_calls:
            response = Client().chat(
                model="llama3.2:latest",
                tools=tool_dict.values(),
                messages=messages,
            )
            tool_calls = False

            for tool in response.message.tool_calls or []:
                try:
                    tool_func = tool_dict.get(tool.function.name)
                    tool_return_value = tool_func(**tool.function.arguments)
                    messages.append(
                        {"role": "tool", "content": json.dumps(tool_return_value)}
                    )
                except Exception as e:
                    print(f"Failed to call {tool}: {e}")
                    messages.append({"role": "tool", "content": str(e)})
                tool_calls = True

        print(messages)
        print("***", response.message.content, "***")


if __name__ == "__main__":
    # print(tools(pathlib.Path("."), None)[0]())
    rudimentary_chat(
        "How can I add new functions to make this code search more intelligent?",
        path="grip-no-tests",
    )
