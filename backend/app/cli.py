"""Chat with the agent in the terminal.

  uv run python -m app.cli                       # interactive
  uv run python -m app.cli "q1" "follow-up"      # scripted: runs the turns in one session, then exits
"""

import sys

from app.services.agent import Session, run_turn

DIM, RESET = "\033[2m", "\033[0m"


def ask(session: Session, q: str) -> None:
    print("bot> ", end="", flush=True)
    for ev in run_turn(session, q):
        match ev["type"]:
            case "token":
                print(ev["text"], end="", flush=True)
            case "tool_call":
                print(f"\n{DIM}  -> {ev['name']}({ev['args']}){RESET}", end="", flush=True)
            case "tool_result":
                print(f"\n{DIM}  <- {ev['summary']} [{ev['ms']}ms]{RESET}\nbot> ", end="", flush=True)
            case "products" if ev["items"]:
                print(f"\n{DIM}  [cards: {', '.join(p['model_number'] for p in ev['items'])}]{RESET}", end="")
            case "error":
                print(f"\n!! {ev['message']}", end="")
    print()


def main() -> None:
    session = Session()
    if len(sys.argv) > 1:
        for q in sys.argv[1:]:
            print(f"\nyou> {q}")
            ask(session, q)
        return
    while True:
        try:
            q = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if q:
            ask(session, q)


if __name__ == "__main__":
    main()
