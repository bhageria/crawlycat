import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "web":
        sys.argv.pop(1)  # remove 'web' so Flask doesn't see it
        from .web import main as web_main
        web_main()
    elif len(sys.argv) > 1 and sys.argv[1] == "gui":
        sys.argv.pop(1)
        from .gui import main as gui_main
        gui_main()
    else:
        from .cli import main as cli_main
        cli_main()
