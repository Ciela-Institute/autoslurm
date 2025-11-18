from __future__ import annotations

import typer

app = typer.Typer(help="Example galaxy training CLI used in integration tests.")


@app.callback(invoke_without_command=True)
def train(
    dataset: str = typer.Option(..., help="Path to the galaxy dataset."),
    epochs: int = typer.Option(10, help="Number of training epochs."),
    learning_rate: float = typer.Option(1e-4, help="Learning rate for Adam optimizer."),
    conditional: bool = typer.Option(False, help="Train a conditional model."),
):
    print(f"dataset={dataset}")
    print(f"epochs={epochs}")
    print(f"learning_rate={learning_rate}")
    print(f"conditional={conditional}")


if __name__ == "__main__":
    app()
