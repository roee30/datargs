# datargs
Create type-safe command line argument parsers from attrs and dataclass classes.

## Usage
Create a dataclass (or an `attrs` class) describing your command line interface, and just call
`datargs.parse()` with the class:

```python
# script.py
from dataclasses import dataclass
from pathlib import Path
from datargs import parse

@dataclass
class Args:
    url: str
    output_path: Path
    verbose: bool
    retries: int = 3

def main():
    args: Args = parse(Args)
    print(args)

if __name__ == "__main__":
    main()
```

Mypy is happy (and so is Pycharm):
```bash
$ mypy script.py
Success: no issues found in 1 source file
```

Your script is good to go!
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

You can use `attr.s` if you prefer:
```pycon
>>> import attr, datargs
>>> @attr.s
... class Args:
...     flag: bool = attr.ib()
>>> datargs.parse(Args, [])
Args(flag=False)
```

Additional `ArgumentParser.add_argument()` parameters are taken from `metadata`:

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

`arg` is a replacement for field that puts `add_argument()` parameters in `metadata`. Use it to save precious keystrokes:
```pycon
>>> from dataclasses import dataclass
>>> from datargs import parse, arg
>>> @dataclass
... class Args:
...     retries: int = arg(default=3, help="number of retries", aliases=["-r"], metavar="RETRIES")
...     # perhaps many more...
>>> parse(Args, ["-h"])
# exactly the same as before
```

And `argsclass` is a `dataclass` alias for extra style points:
```python
from datargs import argsclass, args
@argsclass
class Args:
    flag: bool = arg(help="MY FLAG")
```

To add program descriptions etc. pass your own parser to `parse()`:
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
>>> @datargs
... class Args:
...     ...
>>> parser = make_parser(Args)  # pass `parser=...` to modify an existing parser
```

## Features
- supports typing: code is statically checked to be correct
- comptability with both `dataclass` and `attrs`
- `args` supports all `field` and `attr.ib` arguments.
- support for enums (passed by name):
    ```pycon
    >>> import enum, attr, datargs
    >>> class FoodEnum(enum.Enum):
    ...     ham = 0
    ...     spam = 1
    >>> @attr.dataclass
    ... class Args:
    ...     food: FoodEnum
    >>> datargs.parse(Args, ["--food", "eggs"])
    Args(food=<FoodEnum.ham: 0>)
    >>> datargs.parse(Args, ["--food", "eggs"])
    usage: enum_test.py [-h] --food {ham,spam}
    enum_test.py: error: argument --food: invalid choice: 'eggs' (choose from ['ham', 'spam'])
    ```

## "Why not"s and design choices
There are many libraries out there that do similar things. This list serves as documentation for existing solutions and differences.

So, why not...

### Just use argparse?
That's easy. The interface is clumsy and repetitive, a.k.a boilerplate. Additionally, `ArgumentParser.parse_args()` returns a `Namespace`, which is basically 
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
Let's say you for some reason `--url` is changed to `--uri`:
```python
parser.add_argument("--uri")
...
print(args.url)  # oops
```
You won't discover you made a mistake until you run the code. With `datargs`, a static type checker will issue an error.
Also, why use a carriage when you have a spaceship?

### Use [`click`](https://click.palletsprojects.com/en/7.x/)?
`click` is a great library, but I believe user interface should not be coupled with implementation.

### Use [`simple-parsing`](https://pypi.org/project/simple-parsing/)?
This is another impressive libarary. The drawbacks for me are:
* argument documentation uses introspection hacks and has multiple ways to be used
* options are always nested
* underscores in argument names (`--like_this`)
An upside is that it lets you use your own parser, an important feature for composability and easy modification.

### Use [`argparse-dataclass`](https://pypi.org/project/argparse-dataclass/)?
It's very similar to this library. The main differences I found are:
* no `attrs` support
* not on github, so who you gonna call?

### Use [`argparse-dataclasses`](https://pypi.org/project/argparse-dataclasses/)?
Sams points `argparse-dataclass` but also [Uses inheritance](https://refactoring.guru/replace-inheritance-with-delegation).
