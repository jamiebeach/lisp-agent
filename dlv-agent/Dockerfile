# DLV agent in a box.
#
# Build:
#   docker build -t dlv-agent .
#
# Run (interactive session, memory persisted to host):
#   docker run -it --rm \
#     -e OPENROUTER_API_KEY=sk-or-... \
#     -v "$(pwd)/data:/agent/data" \
#     dlv-agent
#
# Then at the prompt:
#   run("Find a Hamiltonian cycle: edges 1-2, 2-3, 3-4, 4-1, 1-3.")
#   run("My name is Jamie.")
#   forget()

FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# DLV is distributed from https://www.dlvsystem.it as a static Linux binary.
# Swap DLV_URL if the mirror or build name changes.
ARG DLV_URL=https://www.dlvsystem.it/files/dlv.x86-64-linux-elf-static.bin
RUN curl -fsSL -o /usr/local/bin/dlv "$DLV_URL" \
 && chmod +x /usr/local/bin/dlv

WORKDIR /agent
COPY agent.dlv host.py ./

# Keep memory.json inside a mountable directory so it survives the container.
ENV AGENT_MEMORY=/agent/data/memory.json
RUN mkdir -p /agent/data

# Drop into a Python session with run()/forget() bound. This is the "login",
# the same spirit as the Lisp agent dropping you at a live SBCL REPL.
ENTRYPOINT ["python3", "-i", "-c", \
  "from host import run, forget; print('DLV agent ready. Use run(\"...\") and forget().')"]
