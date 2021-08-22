import argparse
import sys

from git2dot import __summary__, __version__
from git2dot.git2dot import getopts, cmdline, parse, gendot, html, gengraph, infov


def cli() -> None:
    """Parse command line arguments and call ``main``.

    This is the interactive (CLI) entry-point to the program.
    """
    # parser = argparse.ArgumentParser(description=__summary__)

    # parser.add_argument(
    #     "--version", default=False, action="store_true", help="Print version"
    # )

    # args = parser.parse_args()

    # if args.version:
    #     print(__version__)
    #     sys.exit(0)

    # opts = vars(args)
    # main(opts)
    main()


def main():
    '''
    main
    '''
    opts = getopts()
    cmdline(opts)
    parse(opts)
    gendot(opts)
    html(opts)
    if opts.png:
        gengraph(opts, 'png')
    if opts.svg:
        gengraph(opts, 'svg')
    infov(opts, 'done')


if __name__ == '__main__':
    main()
