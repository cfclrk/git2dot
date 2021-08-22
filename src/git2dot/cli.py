import argparse
import sys
import os

from git2dot import __summary__, __version__
from git2dot.git2dot import parse, gendot, gengraph, infov

DEFAULT_GITCMD = 'git log --format="|Record:|%h|%p|%d|%ci%n%b"'  # --gitcmd
DEFAULT_RANGE = "--all --topo-order"  # --range


def arg_parser() -> argparse.ArgumentParser:
    """
    Get the command line options using argparse.
    """
    base = os.path.basename(sys.argv[0])
    epilog = r"""EXAMPLES:
   # Example 1: help
   $ {0} -h

   # Example 2: generate a dot file
   $ cd <git-repo>
   $ {0} git.dot

   # Example 3: generate a dot file and a PNG file
   #            you can also run dot manually:
   #               $ dot -v -Tpng -O git.dot
   $ cd <git-repo>
   $ {0} --png git.dot

   # Example 4: generate an HTML file that can supports pan and zoom
   #            you will need to copy in svg-pan-zoom.min.js.
   $ cd <git-repo>
   $ {0} --svg --html index.html git.dot
   $ python -m SimpleHTTPServer 8090  # start a simple server
   $ # browse to URL http://localhost:8090/git.html

   # Example 5: add additional data to each commit node and
   #            generate a png file.
   #            it shows the subject, the commit author,
   #            and the commit date (relative).
   $ cd <git-repo>
   $ {0} --png -l '%h|%s|%cn|%cr' git.dot
   $ ls -1 *.png
   git.dot.png

   # Example 6: limit the history commits since 2017-01-01.
   $ {0} --since 2017-01-01 git.dot

   # Example 7: limit the history commits until 2017-01-01.
   $ {0} --until 2017-01-01 git.dot

   # Example 8: force straight edges instead of splines
   $ {0} --dot-option 'splines="false"' git.dot

   # Example 9. generate a caption table
   #            it contains the current date and directory
   #            the background is light yellow
   #            it uses a fixed with font and is left justified.
   $ {0} --png  -L "<<table border=\\"0\\"><tr><td border=\\"1\\" align=\\"left\\" balign=\\"left\\" bgcolor=\\"lightyellow\\"><font face=\\"courier\\" point-size=\\"9\\">Date: $(date)<br/>Dir:  $(pwd)</font></td></tr></table>>" git.dot

   # Example 10. keep the git output for multiple runs
   #             it shows that you can use the original complex setup
   #             (like custom variables) or any subset.
   #             in this case it generates three additional dot files
   #             with different settings.
   $ {0} --png  -D '@CHID@' 'Change-Id: I([0-9a-z]+)' -l '%h|%s|%cn|%cr|@CHID@' --keep git.dot
   $ ls git.dot*
   git.dot      git.dot.keep     git.dot.png
   $ {0} -i git.dot.keep -D '@CHID@' 'Change-Id: I([0-9a-z]+)' -l '%h|%s|%cn|%cr|@CHID@' [label="{{label}}", color="purple"] git01.dot
   $ {0} -i git.dot.keep -l '%h|%s|%cr' [label="{{label}}", color="green"] git02.dot
   $ {0} -i git.dot.keep -l '%h|%s|%cn|%cr' [label="{{label}}", color="magenta"] git03.dot

   # Example 11: only report the commits associated with three branches:
                 origin/1.0.0, origin/1.0.1 and origin/1.1.0
   $ {0} --choose-branch origin/1.0.0 --choose-branch origin/1.0.1 --choose-branch origin/1.1.0 git01.dot

   # Example 11. change the font name and size for the graph, nodes
   #             and edges.
   $ {0} --png --font-name helvetica --font-size 14.0 git.dot

COPYRIGHT:
   Copyright (c) 2017 Joe Linoff, all rights reserved

LICENSE:
   MIT Open Source

PROJECT:
   https://github.com/jlinoff/git2dot
 """.format(
        base
    )
    afc = argparse.RawTextHelpFormatter
    parser = argparse.ArgumentParser(formatter_class=afc, epilog=epilog)

    parser.add_argument(
        "--version", default=False, action="version", version=__version__
    )

    parser.add_argument(
        "--align-by-date",
        action="store",
        choices=["year", "month", "day", "hour", "minute", "second", "none"],
        default="none",
        help="""Rank the commits by commit date.
The options allow you to specify the relative positions of nodes with
earlier and later commit dates.  When you specify one of the options
(other than none), the earlier node will always be to the left of the
later node.

   year    Compare years.
   month   Compare years and months.
   day     Compare years, months and days.
   hour    Compare years, months, days and hours.
   minute  Compare years, months, days, hours and minutes.
   second  Compare years, months, days, hours, minutes and seconds.
   none    Do not position by date. Earlier nodes can appear to the
           right of later nodes.

The align operation is different than a rank operation. It merely
guarantees that all nodes later than a node appear to the right of
it. This is done by creating invisible edges.

Be careful when using this option. The invisible edge can cause
nodes to not aligh horizontally which can be a bit jarring.

Default: %(default)s
 """,
    )

    parser.add_argument(
        "--bedge",
        action="store",
        metavar=("DOT_ATTR_LIST"),
        default='[arrowhead=normal, color="lightblue", dir=none]',
        help="""Define the bedge attributes.
The bedge is any edge that connects to or from a bnode (see --bnode for details).

Unlike edges that connect cnodes, mnodes and snodes, this is a simple
connection. The parent reference is obvious because of the rank.

Default: %(default)s
 """,
    )

    parser.add_argument(
        "--bnode",
        action="store",
        metavar=("DOT_ATTR_LIST"),
        default='[label="{label}", color="lightblue", style=filled, shape=box, height=0.15]',
        help="""Define the bnode attributes.
The bnode is a branch entry for a cnode, mnode or snode. It is only
associated with the node where it was specified as a ref by git.

It always appears at the same rank level as the associated commit node
and normally appears below it.

This node has a different shape by default because it is really an
attribute of a commit node.

See the documentation for --cnode for more attribute details.

Default: %(default)s
 """,
    )

    parser.add_argument(
        "--choose-branch",
        action="append",
        metavar=("BRANCH"),
        default=[],
        help="""Choose a branch to include.
By default all branches are included. When you select this option, you
limit the output to commit nodes that are in the branch parent chain.

You can use it to select multiple branches to graph which basically
tells the tool to prune all other branches as endpoints.

This is very useful for comparing commits between related branches.
 """,
    )

    parser.add_argument(
        "--choose-tag",
        action="append",
        metavar=("TAG"),
        default=[],
        help="""Choose a tag to include.
By default all tags are included. When you select this option, you
limit the output to commit nodes that are in the tag parent chain.

You can use it to select multiple tags to graph which basically
tells the tool to prune all other tags as endpoints.

This is very useful for comparing commits between related tags.

Make sure that you specify --branch-tag 'tag: TAGNAME' to match
what appears in git.
 """,
    )

    parser.add_argument(
        "--cnode-pedge",
        action="store",
        metavar=("DOT_ATTR_LIST"),
        default="",
        help="""Define the commit node parent edge.
The cnode-pedge is any edge that connects a commit node to its parent.

Empty use the default edge settings.

Default: %(default)s
 """,
    )

    parser.add_argument(
        "--cnode",
        action="store",
        metavar=("DOT_ATTR_LIST"),
        default='[label="{label}", color="bisque"]',
        help="""Define the cnode attributes.
The cnode is a commit node which is a git commit that has a single child.

The variable {label} is generated internally. You have complete
control over everything else.

For example, to change the color to green do this:

   --cnode '[label="{label}", shape=ellipse, fontsize=10.0, color="green", style="filled"]

Or to change the shape and fillcolor:

   --cnode '[label="{label}", shape=diamon, fontsize=10.0, color="red", fillcolor="green", style="solid"]

The available attributes are described here: http://www.graphviz.org/doc/info/attrs.html.

Default: %(default)s
 """,
    )

    parser.add_argument(
        "-c",
        "--crunch",
        action="store_true",
        help="""Crunch branches and tags.
Crunch branches into a single node and tags into a single.
This works around unwieldy placements of the individual
nodes by dot in large graphs.
 """,
    )

    x = [
        'graph[rankdir="LR", fontsize=10.0, bgcolor="white"]',
        'node[shape=ellipse, fontsize=10.0, style="filled"]',
        'edge[weight=2, penwidth=1.0, fontsize=10.0, arrowtail="open", dir="back"]',
    ]
    parser.add_argument(
        "-d",
        "--dot-option",
        action="append",
        default=x,
        metavar=("OPTION"),
        help="""Additional dot options.
For example, to force straight edges add this:

   -d 'splines="false"'

Do not worry about appending a semi-colon. It will be added
automatically.

You can use this to define default top level attributes like
rankdir=LR or the default fontsize to use for all nodes.

Default:
   -d '{}'
 """.format(
            "'\n   -d '".join(x)
        ),
    )

    parser.add_argument(
        "-D",
        "--define-var",
        action="append",
        nargs=2,
        metavar=("KEY", "RE"),
        help="""Define a variable.
Variables are custom data that can be referenced in the commit node
label specification.

This option allows you to extract a value from the commit log
and use it. It is useful for cases where teams have meta-tags
in comments.

Here is an example that shows how to extract change ids of the
form: "Change-Id: I<hex>" and reference it by the name @CHID@.

   -D '@CHID@' 'Change-Id: I([0-9a-z]+)'

You can then reference it like this:

   -l '%s|%ci|@CHID@'

It is best to define the variable as something that is highly unlikely
to occur either in the comments or in the git format specification.

For example, never use % or | or { or } in variable names. Always
surround them with a delimiter like @FOO@.  If you simply specify
@FOO, then this will match @FOO, @FOOBAR and anything else that
contains @FOO which is probably not what you want.
 """.replace(
            "%", "%%"
        ),
    )

    parser.add_argument(
        "--font-name",
        action="store",
        type=str,
        default="",
        help="""Change the font name of graph, node and edge objects.
Here is an example: --font-name helvetica.
 """,
    )

    parser.add_argument(
        "--font-size",
        action="store",
        type=str,
        default="",
        help="""Change the font size of graph, node and edge objects.
Here is an example: --font-size 14.0.
 """,
    )

    parser.add_argument(
        "-g",
        "--gitcmd",
        action="store",
        type=str,
        default=DEFAULT_GITCMD.replace("%", "%%"),
        help="""Base command for generating the graph data.
If you override this command, make sure that the output syntax is the
same as the default command.

The example below shows a simple gitcmd that sets since:

      -g 'git log --format="|Record:|%h|%p|%d|%ci%n%b" --since 2016-01-01 --all --topo-order'

This is very powerful, you can specify any git command at all to
replace git-log but if you do, remember that you must set up the
correct fields for parsing for everything, including cnode labels.

This option disables the --range, --since and --until options.

Default: %(default)s
 """.replace(
            "%", "%%"
        ),
    )

    parser.add_argument(
        "-i",
        "--input",
        action="store",
        metavar=("FILE"),
        default="",
        help="""Input data.
You can use this to avoid running git commands.
It is useful for testing.
 """,
    )

    parser.add_argument(
        "-k",
        "--keep",
        action="store_true",
        help="""Keep the git command output for re-use.
This is great for trying out different display options or for
sharing.

The kept output file name is DOT_FILE.keep.
 """,
    )

    parser.add_argument(
        "-l",
        "--cnode-label",
        action="store",
        metavar=("LABEL_SPEC"),
        # default='%h'.replace('%', '%%'),
        default="%h",
        help="""Define the label used to identify cnodes, mnodes and snodes in the
graph.

Lines are separated by "|"'s. The contents of a line can be a git
format specification like %s or a variable defined by -D like @CHID@
or simply text.

Here is an example that defines the first line as the abbrieviated
commit hash, the second line as the commit subject, the third line as
the date is ISO-8601 format and the fourth line as the @CHID@ value:

   -l '%h|%s|%ci|@CHID@'

If you specify -l '', there will be no labels which is not very
useful.

You can specify the maximum width of a line using -w.

Default: %(default)s
 """.replace(
            "%", "%%"
        ),
    )

    parser.add_argument(
        "-L",
        "--graph-label",
        action="store",
        metavar=("DOT_LABEL"),
        help="""Define a graph label.
This is a convenience option that could be also be speficied as -d
'graph=[label="..."]'. It is used to define labels for the graph.

The labels can be quite complex. The following example shows how
to build a label that is actually an HTML-like table.

   -L "<<table border=\\"0\\"><tr><td border=\\"1\\" align=\\"left\\" balign=\\"left\\" bgcolor=\\"lightyellow\\"><font face=\\"courier\\" point-size=\\"9\\">Date: $(date)<br/>Dir:  $(pwd)</font></td></tr></table>>"

The result is a left justified, fixed font output with a small border
that displays the date and directory that the graph was created in.
 """,
    )

    parser.add_argument(
        "--mnode-pedge",
        action="store",
        metavar=("DOT_ATTR_LIST"),
        default="",
        help="""Define the merge node parent edge.
The mnode-pedgeis any edge that connects a merge node to its parent.

Empty use the default edge settings.

Default: %(default)s
 """,
    )

    parser.add_argument(
        "--mnode",
        action="store",
        metavar=("DOT_ATTR_LIST"),
        default='[label="{label}", color="lightpink"]',
        help="""Define the mnode attributes.
The mnode is a commit node which is a commit that has more than one
child. It can only be created by a git merge operation.

See the documentation for --cnode for more attribute details.

Default: %(default)s
 """,
    )

    parser.add_argument(
        "--png",
        action="store_true",
        help="""Use dot to generate a PNG file.
This is the same as running "dot -Tpng -O FILE.dot".
 """,
    )

    parser.add_argument(
        "--range",
        action="store",
        metavar=("GIT-RANGE"),
        default=DEFAULT_RANGE,
        help="""Only consider git commits that fall within the range.
These are command line arguments used for defining the range.
By default use all commits in the range.

You can add any git log command line options that you want.

For example, you could specify

   --range "--since 2016-01-01"

instead of

   --since 2016-01-01.

This option is ignored if -g is specified.

Default: %(default)s
 """,
    )

    parser.add_argument(
        "-s",
        "--squash",
        action="store_true",
        help="""Squash sequences of simple commits into a single commit.
The default is not to squash.
 """,
    )

    parser.add_argument(
        "--since",
        action="store",
        metavar=("DATE"),
        default="",
        help="""Only consider git commits since the specified date.
This is the same as the --since option to git log.
The default is since the first commit.
This option is ignored if -g is specified.
 """,
    )

    parser.add_argument(
        "--sedge",
        action="store",
        metavar=("DOT_ATTR_LIST"),
        default='[label="{label}", style=dotted, arrowhead="none", dir="none"]',
        help="""Define the sedge attributes.
The sedge is any edge that connects the head and tail squashed nodes
(see --snode for details).

Typically this is a dotted line with a count of the number of nodes
that were squashed.

Default: %(default)s
 """,
    )

    parser.add_argument(
        "--snode",
        action="store",
        metavar=("DOT_ATTR_LIST"),
        default='[label="{label}", color="tomato"]',
        help="""Define the snode attributes.
The snode defines the head and tail nodes of a squashed node sequence.

See the documentation for --cnode for more attribute details.

See the documentation for -s for squash details.
 """,
    )

    parser.add_argument(
        "--svg",
        action="store_true",
        help="""Use dot to generate a SVG file.
This is the same as running "dot -Tsvg -O FILE.dot".
 """,
    )

    parser.add_argument(
        "--tedge",
        action="store",
        metavar=("DOT_ATTR_LIST"),
        default='[arrowhead=normal, color="thistle", dir=none]',
        help="""Define the tedge attributes.
The tedge is any edge that connects to or from a tnode (see --tnode for details).

Unlike edges that connect cnodes, mnodes and snodes, this is a simple
connection. The parent reference is obvious because of the rank.

Default: %(default)s
 """,
    )

    parser.add_argument(
        "--tnode",
        action="store",
        metavar=("DOT_ATTR_LIST"),
        default='[label="{label}", color="thistle", style=filled, shape=box, height=0.15]',
        help="""Define the tnode attributes.
The tnode is a tag entry for a cnode, mnode or snode. It is only
associated with the node where it was specified as a ref by git.

It always appears at the same rank level as the associated commit node
and normally appears above it.

This node has a different shape by default because it is really an
attribute of a commit node.

See the documentation for --cnode for more attribute details.

Default: %(default)s
 """,
    )

    parser.add_argument(
        "--until",
        action="store",
        metavar=("DATE"),
        default="",
        help="""Only consider git commits until the specified date.
This is the same as the --until option to git log.
The default is until the last commit.
This option is ignored if -g is specified.
 """,
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="""Increase the level of verbosity.
-v    shows the basic steps
-v -v shows a lot of output for debugging
 """,
    )

    parser.add_argument(
        "-w",
        "--cnode-label-maxwidth",
        action="store",
        type=int,
        metavar=("WIDTH"),
        default=32,
        help="""Maximum width of a line for a cnode label.
See -l for more details.
 """,
    )

    parser.add_argument(
        "-x",
        "--cnode-label-recid",
        action="store",
        metavar=("STRING"),
        default="@@@git2dot-label@@@:",
        help="""Record identifier for cnode-label fields.
When -l is specified, an extra set of format data is appended to the
gitcmd (-g). This data must be uniquely identified so this option is
used to define the record. It must not appear as random text in a git
comment so it must be odd.

Default: %(default)s
""",
    )

    # Positional arguments at the end.
    parser.add_argument(
        "-o",
        "--outfile",
        type=str,
        help="Write output to a file."
    )

    return parser


def cmdline(opts):
    """
    Re-generate the command line as a string.
    """
    if opts.verbose:
        cli = []
        qs = [" ", "\t", "|", "?", "$", "#"]  # tokens that will trigger a quote
        for arg in sys.argv:
            arg = arg.replace("\\", "\\\\").replace('"', '\\"')
            q = False
            for q in qs:
                if q in arg:
                    arg = '"' + arg + '"'
                    break
            cli.append(arg)
        cmd = " ".join(cli)
        infov(opts, "cmdline = {}".format(cmd))


def cli() -> None:
    """Parse command line arguments and call main.

    This is the interactive (CLI) entry-point to the program.
    """
    parser = arg_parser()
    args = parser.parse_args()
    main(args)


def main(opts: argparse.Namespace):
    cmdline(opts)
    parse(opts)

    # TODO: this should return a string
    gendot(opts)

    # TODO: pass string to these functions
    if opts.png:
        gengraph(opts, "png")
    if opts.svg:
        gengraph(opts, "svg")

    # TODO: if outfile is specified, write to that file

    infov(opts, "done")


if __name__ == "__main__":
    cli()
