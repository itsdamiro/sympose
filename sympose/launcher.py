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
    from sympose import job_timer

    job_timer.start()  # jobs that came due while the app was closed run now, the rest as their time comes (ADR 091)
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
    if args.fix:
        return vault_command.fix(args.persona)
    args.vault_parser.print_help()
    return 0


def _run_jobs(args: argparse.Namespace) -> int:
    from sympose import job_launchd, job_run
    from sympose.envfile import load_env

    load_env()
    if bool(args.job) == args.due:
        args.run_parser.print_help()
        return 0 if not args.job and not args.due else 1
    if args.due:
        job_launchd.rotate_log()
        outcomes = job_run.run_due()
    else:
        handle, _, name = args.job.partition("/")
        if not name:
            print("sympose run: name the job as persona/job, like samantha/weekly-review", file=sys.stderr)
            return 1
        outcomes = [job_run.run(handle, name, manual=True)]
    for outcome in outcomes:
        print(f"{outcome.job}: {outcome.status}" + (f" ({outcome.detail})" if outcome.detail else ""))
    return 1 if any(o.status != job_run.RAN for o in outcomes) and not args.due else 0


def _run_schedule(args: argparse.Namespace) -> int:
    from sympose import job_launchd

    if not job_launchd.supported():
        print("sympose schedule: running jobs while Sympose is closed is only set up for macOS so far.", file=sys.stderr)
        return 1
    try:
        if args.action == "install":
            job_launchd.install()
            print(f"Installed: due jobs run every {job_launchd.EVERY_SECONDS // 60} minutes ({job_launchd.plist_path()}).")
        elif args.action == "remove":
            job_launchd.remove()
            print("Removed: jobs run only while the web app is open.")
        else:
            print("Installed." if job_launchd.installed() else "Not installed: jobs run only while the web app is open.")
    except job_launchd.ScheduleRefused as e:
        print(f"sympose schedule: {e}", file=sys.stderr)
        return 1
    return 0


def _run_slack(args: argparse.Namespace) -> int:
    from sympose.envfile import load_env

    load_env()
    from sympose import slack_connect

    if args.slack_command == "manifest":
        return slack_connect.manifest(args.handle)
    return slack_connect.run()


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
    vault = commands.add_parser("vault", help="look at your notes: --health reports on them, --fix offers each repair, --draft drafts a folder's definition")
    what = vault.add_mutually_exclusive_group()
    what.add_argument("--health", action="store_true", help="report empty notes, links to no note, titles that are not the file name and files that are not notes (changes nothing)")
    what.add_argument("--fix", action="store_true", help="offer each repair one at a time (rename a note to its title, point a link at the folder its note moved to, add a folder's icon) and make it only if you say yes")
    what.add_argument("--draft", metavar="FOLDER", help="draft the definition note of a folder, show it, and write it only if you say yes")
    vault.add_argument("--persona", metavar="HANDLE", help="read what this persona can read (default: the default persona)")
    vault.set_defaults(run=_run_vault, vault_parser=vault)
    run = commands.add_parser("run", help="run scheduled jobs: --due runs the ones whose time has come, persona/job runs one now")
    run.add_argument("job", nargs="?", metavar="PERSONA/JOB", help="run this job now, whatever its schedule")
    run.add_argument("--due", action="store_true", help="run every job whose time has come, then stop")
    run.set_defaults(run=_run_jobs, run_parser=run)
    schedule = commands.add_parser("schedule", help="have the operating system run due jobs while the web app is closed (macOS)")
    schedule.add_argument("action", choices=["install", "remove", "status"], help="install or remove the entry, or say whether it is there")
    schedule.set_defaults(run=_run_schedule)
    slack = commands.add_parser("slack", help="answer in Slack: every persona with a Slack token pair, as its own Slack user (needs Slack switched on in settings)")
    slack.set_defaults(run=_run_slack)
    slack_commands = slack.add_subparsers(dest="slack_command", title="commands")
    manifest = slack_commands.add_parser("manifest", help="print the Slack App manifest of a persona, to paste into Slack when making its App")
    manifest.add_argument("handle", metavar="HANDLE", help="the persona's handle (its folder under profiles/)")
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
