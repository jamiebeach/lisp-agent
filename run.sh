#!/usr/bin/env bash

# Wrap SBCL in rlwrap for better command line editing and history support
# https://gist.github.com/vindarel/2309154f4e751be389fa99239764c363
rlwrap -r -i -b '()' -f completions.txt sbcl --load agent.lisp
