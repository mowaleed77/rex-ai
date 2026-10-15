"""Terminal demo: python apps/cli_demo.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from rex.assistant.engine import RexAssistant, Session

bot, s = RexAssistant(), Session()
print("REX Assistant (type 'quit' to exit)\n")
print("REX:", bot.reply(s, "hello"))
while (m := input("You: ").strip().lower()) not in {"quit", "exit"}:
    print("REX:", bot.reply(s, m))
