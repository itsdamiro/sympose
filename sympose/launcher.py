"""The `sympose` command (docs/decisions/028): `sympose cli` for the terminal chat and `sympose web`
for the web app, the API and the built app together in one process."""

import argparse
import os
import sys


def _run_cli(args: argparse.Namespace) -> int:
    from sympose.cli.__main__ import main as run_cli

    run_cli()
    return 0


def _run_web(args: argparse.Namespace) -> int:
    from sympose.envfile import load_env

    load_env()
    import uvicorn

    from sympose import persona_files, web_static
    from sympose.server import create_app

    try:
        port = args.port if args.port is not None else int(os.getenv("PORT", "8000"))
    except ValueError:
        print(f"sympose web: PORT must be a number, not {os.getenv('PORT')!r}", file=sys.stderr)
        return 1
    app = create_app()
    try:
        web_static.mount_web_app(app)
    except web_static.WebAppMissing as e:
        print(f"sympose web: {e}", file=sys.stderr)
        return 1
    web_static.guard_own_names(app)
    missed = persona_files.missed_notice()  # a persona folder the roster cannot find (ADR 029)
    if missed:
        print(missed, file=sys.stderr)
    address = f"http://127.0.0.1:{port}"
    print(f"Sympose web app: {address}  (Ctrl-C to stop)")
    if args.open:
        import threading
        import webbrowser

        def _open() -> None:
            # A browser failing to open (a headless box, no default browser set) is not worth
            # failing the server over.
            try:
                webbrowser.open(address)
            except webbrowser.Error:
                pass

        # After a short delay rather than before uvicorn.run: opening now would race a browser
        # against a server that has not bound the port yet. uvicorn.run blocks, so this runs on
        # its own thread.
        threading.Timer(1.0, _open).start()
    uvicorn.run(app, host="127.0.0.1", port=port)  # this machine only: no auth, no TLS
    return 0


def _run_doctor(args: argparse.Namespace) -> int:
    from sympose import doctor
    from sympose.envfile import load_env

    load_env()
    return doctor.run(fix=args.fix)


def _run_vault(args: argparse.Namespace) -> int:
    from sympose import vault_command
    from sympose.envfile import load_env

    load_env()
    if args.draft:
        return vault_command.draft(args.draft, args.persona)
    if args.health:
        return vault_command.health(args.persona)
    args.vault_parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sympose", description="Sympose: an AI companion for your Obsidian vault.")
    commands = parser.add_subparsers(dest="command", title="commands")
    cli = commands.add_parser("cli", help="chat with a persona in the terminal")
    cli.set_defaults(run=_run_cli)
    web = commands.add_parser("web", help="open the web app for your vault (on this machine only)")
    web.add_argument("--port", type=int, help="the port to listen on (default: PORT in .env, else 8000)")
    web.add_argument("--open", action="store_true", help="open it in the default browser once it starts")
    web.set_defaults(run=_run_web)
    doctor = commands.add_parser("doctor", help="check the installation and, with --fix, correct what is Sympose's own")
    doctor.add_argument("--fix", action="store_true", help="apply the fixes (persona folder names, wrong-kind settings)")
    doctor.set_defaults(run=_run_doctor)
    vault = commands.add_parser("vault", help="look at your notes: --health reports on them, --draft drafts a folder's definition")
    what = vault.add_mutually_exclusive_group()
    what.add_argument("--health", action="store_true", help="report empty notes, links to no note, titles that are not the file name and files that are not notes (changes nothing)")
    what.add_argument("--draft", metavar="FOLDER", help="draft the definition note of a folder, show it, and write it only if you say yes")
    vault.add_argument("--persona", metavar="HANDLE", help="read what this persona can read (default: the default persona)")
    vault.set_defaults(run=_run_vault, vault_parser=vault)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
