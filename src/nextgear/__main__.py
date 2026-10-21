from .cli import main

if __name__ == "__main__":  # worker processes import this module and must not rerun the CLI
    raise SystemExit(main())
