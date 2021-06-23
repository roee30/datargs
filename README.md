# datargs

A paper-thin wrapper around `argparse` that creates type-safe parsers
from `dataclass` and `attrs` classes.

## Quickstart


Install `datargs`:

```bash
pip install datargs
```

Create a `dataclass` (or an `attrs` class) describing your command line interface, and call
`datargs.parse()` with the class:

```python
# script.py
from dataclasses import dataclass
from pathlib import Path
from datargs import parse

@dataclass  # or @attr.s(auto_attribs=True)
class Args:
    url: str
    output_path: Path
    verbose: bool
    retries: int = 3

def main():
    args = parse(Args)
    print(args)

if __name__ == "__main__":
    main()
```

***(experimental)*** Alternatively: convert an existing parser to a dataclass:
```python
# script.py
parser = ArgumentParser()
parser.add_argument(...)
from datargs import convert
convert(parser)
```

`convert()` prints a class definition to the console.
Copy it to your script.

Mypy and pycharm correctly infer the type of `args` as `Args`, and your script is good to go!
```bash
$ python script.py -h
usage: test.py [-h] --url URL --output-path OUTPUT_PATH [--retries RETRIES]
               [--verbose]

optional arguments:
  -h, --help            show this help message and exit
  --url URL
  --output-path OUTPUT_PATH
  --retries RETRIES
  --verbose
$ python script.py --url "https://..." --output-path out --retries 4 --verbose
Args(url="https://...", output_path=Path("out"), retries=4, verbose=True)
```

## Table of Contents

<!-- toc -->

- [Features](#features)
  * [Static verification](#static-verification)
  * [`dataclass`/`attr.s` agnostic](#dataclassattrs-agnostic)
  * [Aliases](#aliases)
  * [`ArgumentParser` options](#argumentparser-options)
  * [Enums](#enums)
  * [Sequences, Optionals, and Literals](#sequences-optionals-and-literals)
  * [Sub Commands](#sub-commands)
- ["Why not"s and design choices](#why-nots-and-design-choices)
  * [Just use argparse?](#just-use-argparse)
  * [Use `click`](#use-clickhttpsclickpalletsprojectscomen7x)?
  * [Use `clout`](#use-clouthttpscloutreadthedocsioenlatestindexhtml)?
  * [Use `simple-parsing`](#use-simple-parsinghttpspypiorgprojectsimple-parsing)?
  * [Use `argparse-dataclass`](#use-argparse-dataclasshttpspypiorgprojectargparse-dataclass)?
  * [Use `argparse-dataclasses`](#use-argparse-dataclasseshttpspypiorgprojectargparse-dataclasses)?
- [FAQs](#faqs)
  * [Is this cross-platform?](#is-this-cross-platform)
  * [Why are mutually exclusive options not supported?](#why-are-mutually-exclusive-options-not-supported)

<!-- tocstop -->

## Features

### Static verification
Mypy/Pycharm have your back when you when you make a mistake:
```python
...
def main():
    args = parse(Args)
    args.urll  # typo
...
```
Pycharm says: `Unresolved attribute reference 'urll' for class 'Args'`.

Mypy says: `script.py:15: error: "Args" has no attribute "urll"; maybe "url"?`


### `dataclass`/`attr.s` agnostic
```pycon
>>> import attr, datargs
>>> @attr.s
... class Args:
...     flag: bool = attr.ib()
>>> datargs.parse(Args, [])
Args(flag=False)
```

### Aliases
Aliases and `ArgumentParser.add_argument()` parameters are taken from `metadata`:

```pycon
>>> from dataclasses import dataclass, field
>>> from datargs import parse
>>> @dataclass
... class Args:
...     retries: int = field(default=3, metadata=dict(help="number of retries", aliases=["-r"], metavar="RETRIES"))
>>> parse(Args, ["-h"])
usage: ...
optional arguments:
  -h, --help            show this help message and exit
  --retries RETRIES, -r RETRIES
>>> parse(Args, ["-r", "4"])
Args(retries=4)
```

`arg` is a replacement for `field` that puts `add_argument()` parameters in `metadata`.
Use it to save precious keystrokes:
```pycon
>>> from dataclasses import dataclass
>>> from datargs import parse, arg
>>> @dataclass
... class Args:
...     retries: int = arg(default=3, help="number of retries", aliases=["-r"], metavar="RETRIES")
>>> parse(Args, ["-h"])
# exactly the same as before
```

**NOTE**: `arg()` does not currently work with `attr.s`.

`arg()` also supports all `field`/`attr.ib()` keyword arguments.


### `ArgumentParser` options
You can pass `ArgumnetParser` keyword arguments to `argsclass`.
Description is its own parameter - the rest are passed as the `parser_params` parameter as a `dict`.

When a class is used as a subcommand (see below), `parser_params` are passed to `add_parser`, including `aliases`.
```pycon
>>> from datargs import parse, argsclass
>>> @argsclass(description="Romans go home!", parser_params=dict(prog="messiah.py"))
... class Args:
...     flag: bool
>>> parse(Args, ["-h"], parser=parser)
usage: messiah.py [-h] [--flag]
Romans go home!
...
```

or you can pass your own parser:
```pycon
>>> from argparse import ArgumentParser
>>> from datargs import parse, argsclass
>>> @argsclass
... class Args:
...     flag: bool
>>> parser = ArgumentParser(description="Romans go home!", prog="messiah.py")
>>> parse(Args, ["-h"], parser=parser)
usage: messiah.py [-h] [--flag]
Romans go home!
...
```

Use `make_parser()` to create a parser and save it for later:
```pycon
>>> from datargs import make_parser
>>> @dataclass
... class Args:
...     ...
>>> parser = make_parser(Args)  # pass `parser=...` to modify an existing parser
```
**NOTE**: passing your own parser ignores `ArgumentParser` params passed to `argsclass()`.

### Enums
With `datargs`, enums Just Work™:

```pycon
>>> import enum, attr, datargs
>>> class FoodEnum(enum.Enum):
...     ham = 0
...     spam = 1
>>> @attr.dataclass
... class Args:
...     food: FoodEnum
>>> datargs.parse(Args, ["--food", "ham"])
Args(food=<FoodEnum.ham: 0>)
>>> datargs.parse(Args, ["--food", "eggs"])
usage: enum_test.py [-h] --food {ham,spam}
enum_test.py: error: argument --food: invalid choice: 'eggs' (choose from ['ham', 'spam'])
```

**NOTE**: enums are passed by name on the command line and not by value.

## Sequences, Optionals, and Literals
Have a `Sequence` or a `List` of something to
automatically use `nargs`:


```python
from pathlib import Path
from dataclasses import dataclass
from typing import Sequence
from datargs import parse

@dataclass
class Args:
    # same as nargs='*'
    files: Sequence[Path] = ()

args = parse(Args, ["--files", "foo.txt", "bar.txt"])
assert args.files == [Path("foo.txt"), Path("bar.txt")]
```

Specify a list of positional parameters like so:

```python
from datargs import argsclass, arg
@argsclass
class Args:
    arg: Sequence[int] = arg(default=(), positional=True)
```

`Optional` arguments default to `None`:

```python
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datargs import parse

@dataclass
class Args:
    path: Optional[Path]

args = parse(Args, ["--path", "foo.txt"])
assert args.path == Path("foo.txt")

args = parse(Args, [])
assert args.path is None
```

And `Literal` can be used to specify choices:

```python
from pathlib import Path
from dataclasses import dataclass
from typing import Literal
from datargs import parse

@dataclass
class Args:
    path: Literal[Path("foo.txt"), Path("bar.txt")]

args = parse(Args, ["--path", "foo.txt"])
assert args.path == Path("foo.txt")

# Throws an error!
args = parse(Args, ["--path", "bad-option.txt"])
```

### Sub Commands

No need to specify a useless `dest` to dispatch on different commands.
A `Union` of dataclasses/attrs classes automatically becomes a group of subparsers.
The attribute holding the `Union` holds the appropriate instance
upon parsing, making your code type-safe:

```python
import typing, logging
from datargs import argsclass, arg, parse

@argsclass(description="install package")
class Install:
    package: str = arg(positional=True, help="package to install")

@argsclass(description="show all packages")
class Show:
    verbose: bool = arg(help="show extra info")

@argsclass(description="Pip Install Packages!")
class Pip:
    action: typing.Union[Install, Show]
    log: str = None

args = parse(Pip, ["--log", "debug.log", "install", "my_package"])
print(args)
# prints: Pip(action=Install(package='my_package'), log='debug.log')

# Consume arguments:
if args.log:
    logging.basicConfig(filename=args.log)
if isinstance(args.action, Install):
    install_package(args.action.package)
    # static type error: args.action.verbose
elif isinstance(args.action, Show):
    list_all_packages(verbose=args.action.verbose)
else:
    assert False, "Unreachable code"
```
Command name is derived from class name. To change this, use the `name` parameter to `@argsclass`.

As with all other parameters to `add_parser`,
`aliases` can be passed as a key in `parser_params` to add subcommand aliases.

**NOTE**: if the commented-out line above does not issue a type error, try adding an `@dataclass/@attr.s`
before or instead of `@argsclass()`:

```python
@argsclass(description="Pip Install Packages!")  # optional
@dataclass
class Pip:
    action: typing.Union[Install, Show]
    log: str = None
...
if isinstance(args.action, Install):
    install_package(args.action.package)
    # this should now produce a type error: args.action.verbose
```

## "Why not"s and design choices
Many libraries out there do similar things. This list serves as documentation for existing solutions and differences.

So, why not...

### Just use argparse?
That's easy. The interface is clumsy and repetitive, a.k.a boilerplate. Additionally, `ArgumentParser.parse_args()` returns a `Namespace`, which is
equivalent to `Any`, meaning that it any attribute access is legal when type checking. Alas, invalid attribute access will fail at runtime. For example:
```python
def parse_args():
    parser = ArgumentParser()
    parser.add_argument("--url")
    return parser.parse_args()

def main():
    args = parse_args()
    print(args.url)
```

Let's say for some reason `--url` is changed to `--uri`:

```python
parser.add_argument("--uri")
...
print(args.url)  # oops
```
You won't discover you made a mistake until you run the code. With `datargs`, a static type checker will issue an error.
Also, why use a carriage when you have a spaceship?

### Use [`click`](https://click.palletsprojects.com/en/7.x/)?
`click` is a great library. It provides many utilities for command line programs.

Use `datargs` if you believe user interface should not be coupled with implementation, or if you
want to use `argparse` without boilerplate.
Use `click` if you don't care.


### Use [`clout`](https://clout.readthedocs.io/en/latest/index.html)?
It seems that `clout` aims to be an end-to-end solution for command line programs à la click.

Use it if you need a broader solution. Use `datargs` if you want to use `argparse` without boilerplate.

### Use [`simple-parsing`](https://pypi.org/project/simple-parsing/)?
This is another impressive library.

Use it if you have deeply-nested options, or if the following points don't apply
to you.

Use `datargs` if you:
* need `attrs` support
* want as little magic as possible
* don't have many options or they're not nested
* prefer dashes (`--like-this`) over underscores (`--like_this`)

### Use [`argparse-dataclass`](https://pypi.org/project/argparse-dataclass/)?
It's similar to this library. The main differences I found are:
* no `attrs` support
* not on github, so who you gonna call?

### Use [`argparse-dataclasses`](https://pypi.org/project/argparse-dataclasses/)?
Same points `argparse-dataclass` but also [Uses inheritance](https://refactoring.guru/replace-inheritance-with-delegation).

## FAQs
### Is this cross-platform?
Yes, just like `argparse`.
If you find a bug on a certain platform (or any other bug), please report it.

### Why are mutually exclusive options not supported?

This library is based on the idea of a one-to-one correspondence between most parsers
and simple classes. Conceptually, mutually exclusive options are analogous to
[sum types](https://en.wikipedia.org/wiki/Tagged_union), just like [subparsers](#sub-commands) are,
but writing a class for each flag is not ergonomic enough.
Contact me if you want this feature or if you come up with a better solution.
