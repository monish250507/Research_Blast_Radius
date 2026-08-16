import importlib


def load_plugin(name: str):
    return importlib.import_module(f"plugins.{name}")
