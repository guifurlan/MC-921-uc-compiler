# MC-921-uc-compiler
uC compiler built to (MC-921): Compiler construction course  by the Institute of Computing at Unicamp.

## Team:
Guilherme Furlan e Ana Requena

## Requirements

Use Python 3.5 or a newer version.    
Required pip packages:
- ply, pytest, setuptools, graphviz, pathlib, llvmlite

## Running

After you have accepted this assignment on the course's Github Classroom page,
clone it to your machine.

You can run `uc_llvm.py` directly with python. For more information, run:
```sh
    python3 uc/uc_llvm.py -h
```
You can use the inputs available inside
the `tests/in-out/` directory.

The `uc_compiler.py` script is also available, it can be run through its
symbolic link at the root of the repo (`ucc`). For more information, run:
```sh
    ./ucc -h
```

## Testing with Pytest

You can run all the tests in `tests/in-out/` automatically with `pytest`. For
that, you first need to make the source files visible to the tests. There are
two options:
- Install your project in editable mode using the `setup.py` file from the root
  of the repo
```sh
    pip install -e .
```
- Or, add the repo folder to the PYTHONPATH environment variable with `setup.sh`
```sh
    source setup.sh
```

Then you should be able to run all the tests by running `pytest` at the root
of the repo.

### Linting and Formatting

This step is **optional**. Required pip packages:
- flake8, black, isort

You can lint your code with two `flake8` commands from the root of the repo:
```sh
    flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
    flake8 . --count --exit-zero --max-line-length=120 --statistics
```

The first command shows errors that need to be fixed and will cause your
commit to fail. The second shows only warnings that are suggestions for
a good coding style.

To format the code, you can use `isort` to manage the imports and `black`
for the rest of the code. Run both from the root of the repo:
```sh
    isort .
    black .
```

## About

This repository is one of the assignments handed out to the students in the course
"MC921 - Compiler Construction" offered by the Institute of
Computing at Unicamp.
