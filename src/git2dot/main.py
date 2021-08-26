import argparse
import logging
import sys

from git2dot.git2dot import parse, gendot, gengraph

log = logging.getLogger(__name__)


# TODO: main should take a dict
def main(opts: argparse.Namespace):

    # STEPS:
    # git_log = Run git log
    # git_log_ast = Parse git_log
    # pydot_digraph = Transform git_log_ast into a pydot.Dot

    parse(opts)

    dot = gendot(opts)
    out = dot.encode("utf-8")

    if opts.png:
        out = gengraph(opts, dot, "png")
    if opts.svg:
        out = gengraph(opts, dot, "svg")

    # If the "outfile" option is provided, write output to the given file. Otherwise,
    # write output to stdout.
    if opts.outfile:
        with open(opts.outfile, "wb") as f:
            f.write(out)
    else:
        sys.stdout.buffer.write(out)

    log.info("done")
