#!/usr/bin/env python3
"""host.py — the thin host around a DLV agent.

DLV (https://www.dlvsystem.it) is a solver, not a scripting language: it has
no sockets and no event loop. It reads a logic program and prints the answer
sets it entails, then exits. So — exactly like any ASP program — it needs a
host to feed it. This file is that host, and nothing more. It moves bytes:
HTTP in, JSON out, and it shells to `dlv`. Every decision that *matters* is a
DLV answer set:

  * The agent's only tool is a live DLV solver (dlv_solve). Ask it a hard
    combinatorial question and it doesn't recall the answer — it writes an
    ASP encoding and solves it. This is the analog of the Lisp agent's EVAL.
  * Whether the loop continues is decided by agent.dlv, not by Python. The
    host writes the model's turn as facts, runs agent.dlv, and reads back a
    single atom: `recurse` or `stop`.

Usage:
    export OPENROUTER_API_KEY=sk-or-...
    python3 host.py "Color this graph with 3 colors: edges 1-2, 2-3, 3-1, 1-4."

Memory: the full conversation persists to memory.json between runs, so a
later process remembers what an earlier one was told.
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request

# --- configuration --------------------------------------------------------

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.environ.get("AGENT_MODEL", "anthropic/claude-sonnet-4.5")
API_KEY = os.environ.get("OPENROUTER_API_KEY")
MEMORY_FILE = os.environ.get("AGENT_MEMORY", "memory.json")

# Where to find the DLV binary and the loop program that lives beside us.
DLV_BIN = os.environ.get("DLV_BIN", "dlv")
HERE = os.path.dirname(os.path.abspath(__file__))
LOOP_PROGRAM = os.path.join(HERE, "agent.dlv")

# --- running DLV ----------------------------------------------------------
# One helper does all of it: write programs to a temp file, run the solver,
# hand back the answer sets it printed. `-silent` suppresses the banner so
# stdout is just lines of `{atom, atom, ...}`.


def dlv(*programs, filter_pred=None, n=None):
    """Run DLV over the given program strings; return its answer-set lines."""
    args = [DLV_BIN, "-silent"]
    if n is not None:
        args.append("-n=%d" % n)
    if filter_pred is not None:
        args.append("-filter=%s" % filter_pred)
    files = []
    try:
        for program in programs:
            fh = tempfile.NamedTemporaryFile(
                mode="w", suffix=".dlv", delete=False)
            fh.write(program)
            fh.close()
            files.append(fh.name)
        proc = subprocess.run(
            args + files, capture_output=True, text=True, timeout=30)
        out = (proc.stdout or "").strip()
        if proc.returncode != 0 and not out:
            return "ERROR: %s" % (proc.stderr or "dlv exited %d" %
                                  proc.returncode).strip()
        return out
    except FileNotFoundError:
        return ("ERROR: DLV binary %r not found. Set DLV_BIN or install DLV "
                "from https://www.dlvsystem.it" % DLV_BIN)
    except subprocess.TimeoutExpired:
        return "ERROR: DLV timed out"
    finally:
        for name in files:
            try:
                os.unlink(name)
            except OSError:
                pass


# --- the only tool: a live DLV solver -------------------------------------
# Logic is data, data is logic. So instead of a toolbox, the agent gets one
# tool: it writes an ASP program and we solve it. Ask it for a 3-coloring and
# it encodes the constraints and reads off a model.

TOOLS = [{
    "type": "function",
    "function": {
        "name": "dlv_solve",
        "description": (
            "Solve an Answer Set Programming / Datalog program with DLV and "
            "return the answer sets it prints (each as {atom, atom, ...}). "
            "Use this for constraint problems, graph problems, planning, "
            "combinatorial search, deduction — anything declarative. Write "
            "guessing rules with disjunction (a v b :- ...), forbid bad "
            "models with constraints (:- ...), and query with plain rules."),
        "parameters": {
            "type": "object",
            "properties": {
                "program": {
                    "type": "string",
                    "description": (
                        "A complete DLV program, e.g. "
                        "'color(N,red) v color(N,green) v color(N,blue) :- "
                        "node(N). :- edge(A,B), color(A,C), color(B,C). "
                        "node(1). node(2). edge(1,2).'"),
                },
            },
            "required": ["program"],
        },
    },
}]


def dlv_solve(program):
    """The agent's hands: solve the ASP program, print what came back."""
    result = dlv(program)
    return result if result else "No answer set (the program is unsatisfiable)."


def execute(tool_call):
    """Turn one tool-call from the model into a tool-result message."""
    name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"]["arguments"])
    if name == "dlv_solve":
        result = dlv_solve(args["program"])
    else:
        result = "ERROR: unknown tool %s" % name
    print("  \u21b3 %s => %s" % (args.get("program", ""), result))
    return {
        "role": "tool",
        "tool_call_id": tool_call["id"],
        "content": result,
    }


# --- talking to the model -------------------------------------------------


def call_model(messages):
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
    }).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={
            "Authorization": "Bearer " + (API_KEY or ""),
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


# --- the loop itself, decided by DLV --------------------------------------
# An agent is a recursive function over a growing list of messages. The Lisp
# agent writes that recursion in Lisp. Here, the one branch that defines the
# loop — recurse vs. stop — is delegated to agent.dlv. We encode the model's
# turn as facts, ask DLV what to do, and act on its answer set.


def dlv_says_recurse(message):
    """Ask agent.dlv whether this turn's tool calls mean 'recurse'."""
    tool_calls = message.get("tool_calls") or []
    facts = "".join(
        'tool_call(%s, %s).\n' % (_atom(tc["id"]),
                                  _atom(tc["function"]["name"]))
        for tc in tool_calls)
    answer = dlv(facts, filter_pred="recurse,stop", n=1)
    return "recurse" in answer


def _atom(text):
    """Quote a Python string as a DLV string constant."""
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def agent_loop(messages):
    """Return the complete message history, final answer included.

    Base case: DLV derives `stop` (the model answered in words).
    Recursive case: DLV derives `recurse`; run the tools and recur.
    """
    message = call_model(messages)["choices"][0]["message"]
    if dlv_says_recurse(message):
        results = [execute(tc) for tc in message["tool_calls"]]
        return agent_loop(messages + [message] + results)
    return messages + [message]


# --- memory ---------------------------------------------------------------
# Messages are already JSON in spirit, so memory is just writing that list
# down and reading it back. Recall, recur, remember.

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You are a helpful agent whose only tool is a live DLV solver "
        "(Answer Set Programming / Datalog). Prefer encoding problems as ASP "
        "and solving them with dlv_solve over guessing. Your conversation "
        "history persists across sessions."),
}


def remember(messages):
    with open(MEMORY_FILE, "w") as out:
        json.dump(messages, out)
    return messages


def recall():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as inp:
            return json.load(inp)
    return [SYSTEM_MESSAGE]


def forget():
    if os.path.exists(MEMORY_FILE):
        os.unlink(MEMORY_FILE)
    print("Memory wiped.")


# --- entry point ----------------------------------------------------------


def run(prompt):
    history = remember(
        agent_loop(recall() + [{"role": "user", "content": prompt}]))
    print(history[-1].get("content") or "")


def main(argv):
    if len(argv) == 2 and argv[1] == "forget":
        forget()
        return
    if len(argv) < 2:
        print('usage: host.py "your prompt"   |   host.py forget',
              file=sys.stderr)
        sys.exit(2)
    if not API_KEY:
        print("error: set OPENROUTER_API_KEY", file=sys.stderr)
        sys.exit(2)
    run(" ".join(argv[1:]))


if __name__ == "__main__":
    main(sys.argv)
