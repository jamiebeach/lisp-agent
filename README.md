# lisp-agent

> "LISP is the language for AI." — my professor, circa 2000

He was right. He was just 25 years early.

This is a complete AI agent in about 100 lines of Common Lisp. Recursive agent loop, one tool (the Lisp REPL itself), and persistent memory in 20 lines. It talks to any model on [OpenRouter](https://openrouter.ai).

No framework. No state machine. No vector database. Just `eval`, `append`, and recursion.

## The whole agent

```lisp
(defun agent-loop (messages)
  (let* ((message (ref (call-model messages) "choices" 0 "message"))
         (tool-calls (gethash "tool_calls" message)))
    (if (and tool-calls (plusp (length tool-calls)))
        (agent-loop (append messages
                            (list message)
                            (map 'list #'execute tool-calls)))
        (append messages (list message)))))
```

Base case: the model answers in words. Recursive case: it asks for tools, we run them and recur with the enriched history. The agent's state is just the argument being folded through the recursion.

## The only tool is eval

Code is data, data is code. So instead of building a bunch of tools, the agent gets one tool: a live Common Lisp REPL.

```lisp
(defun lisp-eval (form-string)
  (handler-case
      (format nil "~s" (eval (read-from-string form-string)))
    (error (e) (format nil "ERROR: ~a" e))))
```

Ask it for the 30th Fibonacci number and it doesn't recall the answer. It writes the loop and runs it.

## Quick start (Docker)

```bash
docker build -t lisp-agent .

docker run -it --rm \
  -e OPENROUTER_API_KEY=sk-or-... \
  -v "$(pwd)/data:/agent/data" \
  lisp-agent
```

You land in a live SBCL REPL with the agent loaded:

```lisp
(agent:run "What is the 30th Fibonacci number? Compute it, don't recall it.")
(agent:run "My name is Jamie.")
```

Exit the container. Come back tomorrow.

```lisp
(agent:run "What's my name?")   ; it remembers
(agent:forget)                  ; wipe the slate
```

## Quick start (bare metal)

Requires [SBCL](https://www.sbcl.org/) and [Quicklisp](https://www.quicklisp.org/).

```bash
export OPENROUTER_API_KEY=sk-or-...
sbcl --load agent.lisp
```

Dependencies (fetched automatically via Quicklisp): [dexador](https://github.com/fukamachi/dexador) for HTTP, [shasht](https://github.com/yitzchak/shasht) for JSON. That's the whole list.

## How memory works

Messages are already a list of hash tables, which is to say, already JSON in spirit. So memory is just writing the list down and reading it back:

```lisp
(remember (agent-loop (append (recall) (list new-user-message))))
```

Recall, recur, remember. No schema, no migrations, no store abstraction. The full transcript (tool calls included) lands in `memory.json`, or wherever `AGENT_MEMORY` points.

Known limitation: it never forgets on its own, so a long-lived conversation will eventually hit the model's context window. The natural fix is a compress step between `recall` and the loop, where the agent summarizes its own past. PRs welcome.

## Configuration

| What | Where | Default |
|------|-------|---------|
| API key | `OPENROUTER_API_KEY` env var | required |
| Model | `*model*` in `agent.lisp` | `anthropic/claude-sonnet-4.5` |
| Memory file | `AGENT_MEMORY` env var | `memory.json` |

Any OpenRouter model that supports tool calling works. Swap `*model*` and nothing else changes.

## ⚠️ Read this before you get clever

`eval` as a tool means the model executes arbitrary code wherever the agent runs. That is the entire point, and also the entire risk. Run it in the container, mount nothing you care about, and treat the host as off limits. This is a toy for a sandbox, not a pattern for production.

## Why

Symbolic AI lost. But the thing LISP was actually built for, programs as data, computation that inspects and transforms itself, turned out to be a pretty good description of what an agent is. The models do the reasoning now. The loop around them is the part LISP was always best at.

Longer version on the blog: [My Prof Was Right About LISP. He Was Just 25 Years Early.](https://thebeach.dev/posts/lisp-agent) *(update slug when published)*

## Files

```
agent.lisp    the agent: loop, tool, memory (~100 lines)
Dockerfile    SBCL + Quicklisp + deps, drops you at a REPL
LICENSE       MIT
```

## License

MIT. Go play.
