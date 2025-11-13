# Register a script

For `autoslurm-schedule` to be able to schedule and run your scripts,
some minimal structure is required.
In short,
a script must be installed in the virtual environment used to submit jobs.
To accomplish this, the script must be registered in the `pyproject.toml` file of a python package
installed in the virtual environment.

Once registered, no further actions are required to run and schedule a script.

## Creating a Package

To create a package, you can follow the instructions in the
[Python Packaging User Guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/).

Here is a suggested `pyproject.toml` template.

```toml
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "name_of_package"
version = "0.1.0"
description = "A short description of my package"
authors = [
    {name="My Name", email="my_name@example.com"},
    ]
requires-python = ">=3.9"

[project.scripts]
...
```

The `pyproject.toml` file must be saved in the root of your project

```
my_package/
├── src/
│   └── name_of_package/
│       ├── __init__.py
│       └── script.py
├── pyproject.toml
└── README.md
```

Once this file is created, you can use the following command from
the root directory of `my_package` to install the package in your virtual environment

```shell
pip install -e .
```

This creates an editable installation of your package in your environment.
This implies that any changes you make to the package will be reflected in your
environment without the need to reinstall the package.


## Registering a Script in `pyproject.toml`

Let's assume the script is located in `my_package` at the following location
```
my_package/
├── src/
    └── name_of_package/
        ├── __init__.py
        └── script.py
```

The function `main()` and `cli()` defined in `script.py` must be registered
in the package's `pyproject.toml` file as follows

```toml
[project.scripts]
my-script     = "name_of_package.script:main"
my-script-cli = "name_of_package.script:cli"
```

A program with the suffix `-cli` must always be registered for each script
to allow `autoslurm-schedule` to capture the command-line arguments of the script.

Once the `main` and `cli` functions are registered,
`my-script` can be scheduled and submitted using the
`autoslurm-schedule` and `autoslurm-submit` commands respectively.
More information on these commands can be found in the [Getting Started](./getting_started.md) section.

## The `main` and `cli` Functions

Some minimal structure is required on your script because `autoslurm-schedule` can only
compile the command-line arguments of your script if a function (which we call `cli`)
prints these arguments on the console.

As a solution, each script will minimally have to be provided with the following cli function (which can be copied verbatim):

```python
def cli():
    import sys, json

    args = parse_args()

    print(json.dumps(vars(args), indent=4))
    sys.exit(0)
```

### `parse_args`

The `parse_args()` function is used to parse the command-line arguments. It is
an effective way to interact with a python script, and works well with
the way we submit jobs. Here is a template to get you started:

```python
def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Your application description here.")
    parser.add_argument("--example", type=str, help="Example argument")

    args = parser.parse_args()
    return args
```


### `main`

Finally, the `main()` function serves as the entry point of your application.
We suggest the following structure

```python
def main():
    import torch

    args = parse_args()

    # Application logic goes here
```

It is recommended to import all the necessary packages inside the `main`
function to avoid slow scheduling of jobs, especially if you have heavy imports
like Pytorch.
