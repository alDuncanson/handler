"""Ollama model management utilities."""

import subprocess


def get_ollama_models() -> list[str]:
    """Get list of locally available Ollama models.

    Returns:
        List of model names available in Ollama
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().split("\n")
        if len(lines) <= 1:
            return []
        return [line.split()[0] for line in lines[1:] if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError, IndexError):
        return []


def check_ollama_model(model: str) -> bool:
    """Check if a specific Ollama model is available locally.

    Args:
        model: The model name to check

    Returns:
        True if the model is available
    """
    available_models = get_ollama_models()
    model_base = model.split(":")[0]
    return any(m == model or m.startswith(f"{model_base}:") for m in available_models)


def prompt_ollama_pull(model: str) -> bool:
    """Prompt user to pull an Ollama model if not available.

    Args:
        model: The model name to pull

    Returns:
        True if pull succeeded or user declined, False on error
    """
    print(f"\nModel '{model}' not found locally.")
    response = input("Would you like to pull it now? [y/N]: ").strip().lower()

    if response not in ("y", "yes"):
        print("Skipping model pull. Server may fail to start.")
        return True

    print(f"\nPulling model {model}...\n")
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            timeout=600,
        )
        if result.returncode == 0:
            print(f"\nSuccessfully pulled {model}\n")
            return True
        print(f"\nFailed to pull {model}\n")
        return False
    except subprocess.TimeoutExpired:
        print(f"\nTimeout pulling {model}\n")
        return False
    except FileNotFoundError:
        print("\nOllama CLI not found. Please install Ollama.\n")
        return False
