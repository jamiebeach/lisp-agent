# dlv-agent

> A clone of [`lisp-agent`](../README.md), rebuilt on [DLV](https://www.dlvsystem.it) — logic programming instead of Lisp.

The Lisp agent's thesis is *programs as data*: its only tool is `eval`, and the
loop around it is recursion. DLV comes at the same idea from the other side.
DLV is a [disjunctive Datalog / Answer Set Programming](https://en.wikipedia.org/wiki/Answer_set_programming)
system — you hand it a logic program and it hands back the *models* that
program entails. **Rules are data, data is rules.** So this clone keeps the
shape of the original and swaps the substrate:

| lisp-agent | dlv-agent |
|------------|-----------|
| the only tool is `eval` (a live Lisp REPL) | the only tool is `dlv_solve` (a live DLV solver) |
| the loop is a recursive Lisp function | the loop's one branch is a DLV answer set |
| ask for Fibonacci, it writes the loop | ask for a 3-coloring, it writes the constraints |
| memory is a list written to `memory.json` | memory is a list written to `memory.json` |

## The honest catch

DLV is a *solver*, not a scripting language. It has no sockets, no event loop,
no way to POST to an API. Like any ASP program, it needs a host to feed it
facts and read back its models. So `dlv-agent` is two files:

- **`agent.dlv`** — the part that is genuinely DLV: the agent's loop, expressed
  declaratively.
- **`host.py`** — ~90 lines of Python standard library that does nothing but
  move bytes: HTTP in, JSON out, and shelling to `dlv`. No `pip install`.

Everything that *matters* is a DLV answer set. The Python just carries water.

## The whole loop (in DLV)

The Lisp agent's loop is a recursive function; its base and recursive cases are
`if` branches. In DLV there are no functions — there is only what the facts
entail. So the loop's single decision isn't coded, it's **derived**:

```prolog
% Recursive case: the model asked for tools.
recurse :- tool_call(_, _).

% Base case: it answered in words. (Negation as failure = the base case.)
stop :- not recurse.
```

Each turn, the host writes the model's response as `tool_call(Id, Name)` facts,
runs `agent.dlv`, and reads back a single atom — `recurse` or `stop`. That atom
*is* the control flow. The Python recursion just carries the growing message
list, exactly as the argument folded through the Lisp recursion.

## The only tool is a solver

Code is data, data is code — so the Lisp agent's one tool is `eval`. Logic is
data, data is logic — so this agent's one tool is `dlv_solve`. The model writes
an ASP program; the host solves it and feeds the answer sets back:

```python
def dlv_solve(program):
    result = dlv(program)          # run the `dlv` binary on the program
    return result or "No answer set (the program is unsatisfiable)."
```

Ask it to 3-color a graph and it doesn't recall an answer. It writes the
guess-and-check:

```prolog
color(N,red) v color(N,green) v color(N,blue) :- node(N).
:- edge(A,B), color(A,C), color(B,C).
```

...and reads a proper coloring straight off the model. Graph problems,
planning, scheduling, Sudoku, deduction — DLV's home turf.

## Quick start (Docker)

```bash
docker build -t dlv-agent .

docker run -it --rm \
  -e OPENROUTER_API_KEY=sk-or-... \
  -v "$(pwd)/data:/agent/data" \
  dlv-agent
```

You land in a Python session with the agent bound:

```python
run("3-color this graph: edges 1-2, 2-3, 3-1, 1-4. Solve it, don't guess.")
run("My name is Jamie.")
```

Exit the container. Come back tomorrow.

```python
run("What's my name?")   # it remembers
forget()                 # wipe the slate
```

## Quick start (bare metal)

Requires [DLV](https://www.dlvsystem.it) on your `PATH` (or point `DLV_BIN` at
it) and Python 3 — no third-party packages.

```bash
export OPENROUTER_API_KEY=sk-or-...
python3 host.py "Find a Hamiltonian cycle over edges 1-2, 2-3, 3-4, 4-1, 1-3."
python3 host.py forget
```

## How memory works

Unchanged from the original, because it was already right: the messages are a
list of JSON-shaped dicts, so memory is just writing the list down and reading
it back. Recall, recur, remember. The full transcript (tool calls included)
lands in `memory.json`, or wherever `AGENT_MEMORY` points.

Same known limitation: it never forgets on its own, so a long conversation will
eventually hit the model's context window.

## Configuration

| What | Where | Default |
|------|-------|---------|
| API key | `OPENROUTER_API_KEY` env var | required |
| Model | `AGENT_MODEL` env var | `anthropic/claude-sonnet-4.5` |
| Memory file | `AGENT_MEMORY` env var | `memory.json` |
| DLV binary | `DLV_BIN` env var | `dlv` |

Any OpenRouter model that supports tool calling works.

## ⚠️ Read this before you get clever

`dlv_solve` runs whatever program the model writes, wherever the agent runs.
DLV is far more contained than a live Lisp `eval` — it computes answer sets, it
doesn't open files or sockets — but a pathological program can still burn CPU
and memory. The host caps each solve at 30 seconds. Run it in the container,
mount nothing you care about, and treat this as a toy for a sandbox.

## Why

The Lisp agent's point is that *programs as data* turned out to be a good
description of an agent. Logic programming makes the same bet from the
declarative side: *what* is true, not *how* to compute it. An agent that reasons
by writing and solving logic programs is an agent whose every step you can read
as a model. The LLM does the reasoning; DLV makes the reasoning checkable.

## Files

```
agent.dlv     the agent loop, declaratively (recurse vs. stop)
host.py       the thin host: HTTP + JSON + memory + shelling to dlv (~90 lines)
Dockerfile    DLV + Python, drops you at an interactive session
LICENSE       MIT
```

## License

MIT. Go play.
