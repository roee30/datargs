from operator import attrgetter
import dataclasses
from argparse import ArgumentParser
from textwrap import indent, dedent
from typing import Tuple


def convert(parser: ArgumentParser):
    print(convert_str(parser))


def convert_str(parser: ArgumentParser) -> str:
    attrs, is_argsclass = get_attrs(parser)
    if is_argsclass:
        header = dedent(
            """
        from datargs import argsclass, arg
        
        
        @argsclass
        class Args:
        """
        )
    else:
        header = dedent(
            f"""
        from dataclasses import dataclass


        @dataclass
        class Args:
        """
        )

    return header + indent(attrs, " " * 4)


def get_attrs(parser: ArgumentParser) -> Tuple[str, bool]:
    def to_var(x):
        return x.strip("-").replace("-", "_")

    seen = set()
    is_argsclass = False
    result = ""
    for action in sorted(parser._actions, key=lambda a: a.default is not None):
        first, *aliases = action.option_strings
        if first in seen or first == "-h":
            continue
        seen.add(first)
        name = to_var(first)
        aliases = list(map(repr, aliases))
        try:
            typ = action.type.__name__
        except AttributeError:
            if action.type is not None:
                raise
            if "StoreTrue" in str(action):
                typ = "bool"
            else:
                typ = action.type or "str"
        if action.nargs:
            typ = f"list[{typ}]"
        relevant_pairs = {
            key: value
            for key, value in vars(action).items()
            if value is not None
            and not isinstance(value, dataclasses._MISSING_TYPE)
            and key
            not in [
                "required",
                "dest",
                "const",
                "option_strings",
                "container",
                "nargs",
                "type",
            ]
        }
        if relevant_pairs.get("deprecated", None) is False:
            relevant_pairs.pop("deprecated")
        rest = [f"{key}={value!r}" for key, value in relevant_pairs.items()]
        result += f"{name}: {typ}"
        if set(relevant_pairs) - {"default"}:
            is_argsclass = True
            result += f" = arg({', '.join(aliases + rest)})"
        elif not action.required:
            default = vars(action).get("default", None)
            result += f" = {default!r}"
        result += "\n"
    return result, is_argsclass


def random_test():
    parser = ArgumentParser()
    parser.add_argument("-a", required=True)
    parser.add_argument("-b", default=3, type=int)
    print(convert(parser))
    parser = ArgumentParser()
    parser.add_argument("-a", required=True, help="help")
    parser.add_argument("-b", default=3, type=int)
    print(convert(parser))
    parser = ArgumentParser()
    parser.add_argument("-a", type=str, required=True, help="help")
    parser.add_argument("-b", default=3, type=int, help="help")
    print(convert(parser))


if __name__ == "__main__":
    main()
