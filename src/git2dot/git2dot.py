import inspect
import re
import subprocess
import sys
from textwrap import dedent
from typing import Optional, Tuple
import logging

import dateutil.parser
import pydot

log = logging.getLogger(__name__)

DEFAULT_GITCMD = 'git log --format="|Record:|%h|%p|%d|%ci%n%b"'  # --gitcmd
DEFAULT_RANGE = "--all --topo-order"  # --range


class Node:
    """
    Each node represents a commit.
    A commit can have zero or parents.
    A parent link is created each time a merge is done.
    """

    m_list = []
    m_map = {}
    m_list_bydate = []
    m_vars_usage = {}  # nodes that have var values

    def __init__(self, cid, pids=[], branches=[], tags=[], dts=None):
        self.m_cid = cid
        self.m_idx = len(Node.m_list)
        self.m_parents = pids
        self.m_label = ""
        self.m_branches = branches
        self.m_tags = tags
        self.m_children = []

        self.m_vars = {}  # user defined variable values

        self.m_choose = True  # used by the --choose-* options only

        self.m_extra = []
        self.m_dts = dts  # date/time stamp, used for invisible constraints.

        # For squashing.
        self.m_chain_head = None
        self.m_chain_tail = None
        self.m_chain_size = -1

        Node.m_list.append(self)
        Node.m_map[cid] = self

    def is_squashable(self):
        if (
            len(self.m_branches) > 0
            or len(self.m_tags) > 0
            or len(self.m_parents) > 1
            or len(self.m_children) > 1
        ):
            return False
        return True

    def is_squashed(self):
        if self.m_chain_head is None:
            return False
        if self.m_chain_tail is None:
            return False
        return (
            self.m_chain_size > 0
            and self.m_cid != self.m_chain_head.m_cid
            and self.m_cid != self.m_chain_tail.m_cid
        )

    def is_squashed_head(self):
        if self.m_chain_head is None:
            return False
        return self.m_chain_head.m_cid == self.m_cid

    def is_squashed_tail(self):
        if self.m_chain_tail is None:
            return False
        return self.m_chain_tail.m_cid == self.m_cid

    def is_merge_node(self):
        return len(self.m_children) > 1

    def find_chain_head(self):
        if self.is_squashable() == False:
            return None
        if self.m_chain_head is not None:
            return self.m_chain_head

        # Get the head node, traversing via parents.
        chain_head = None
        chain_next = self
        while chain_next is not None and chain_next.is_squashable():
            chain_head = chain_next
            if len(chain_next.m_parents) > 0:
                chain_next = Node.m_map[chain_next.m_parents[0]]
            else:
                chain_next = None
        return chain_head

    def find_chain_tail(self):
        if self.is_squashable() == False:
            return None
        if self.m_chain_tail is not None:
            return self.m_chain_tail

        # Get the tail node, traversing via children.
        chain_tail = None
        chain_next = self
        while chain_next is not None and chain_next.is_squashable():
            chain_tail = chain_next
            if len(chain_next.m_children) > 0:
                chain_next = chain_next.m_children[0]
            else:
                chain_next = None
        return chain_tail

    @staticmethod
    def squash():
        """
        Squash nodes that in a chain of single commits.
        """
        update = {}
        for nd in Node.m_list:
            head = nd.find_chain_head()
            if head is not None:
                update[head.m_cid] = head

        for key in update:
            head = update[key]
            tail = head.find_chain_tail()
            cnext = head
            clast = head
            distance = 0
            while clast != tail:
                distance += 1
                clast = cnext
                cnext = cnext.m_children[0]

            cnext = head
            clast = head
            while clast != tail:
                idx = cnext.m_idx
                cid = cnext.m_cid

                Node.m_list[idx].m_chain_head = head
                Node.m_list[idx].m_chain_tail = tail
                Node.m_list[idx].m_chain_size = distance

                Node.m_map[cid].m_chain_head = head
                Node.m_map[cid].m_chain_tail = tail
                Node.m_map[cid].m_chain_size = distance

                clast = cnext
                cnext = cnext.m_children[0]

    def rm_parent(self, pcid):
        while pcid in self.m_parents:
            i = self.m_parents.index(pcid)
            self.m_parents = self.m_parents[:i] + self.m_parents[i + 1 :]

    def rm_child(self, ccid):
        for i, cnd in reversed(list(enumerate(self.m_children))):
            if cnd.m_cid == ccid:
                self.m_children = self.m_children[:i] + self.m_children[i + 1 :]


def runcmd(cmd: str) -> Tuple[int, str]:
    """Execute cmd as a subprocess.

    Return the stdout and exit status.
    """
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            universal_newlines=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as ex:
        msg = dedent(
            f"""
            Error running command: {ex.args}
            Return Code: {ex.returncode}
              [stdout]: {ex.stdout}
              [stderr]: {ex.stderr}
            """
        )
        print(msg)
        raise

    return proc.returncode, proc.stdout

def read(opts):
    """
    Read the input data.
    The input can come from two general sources: the output of a git
    command or a file that contains the output from a git comment
    (-i).
    """
    # Run the git command.
    log.info("Reading git repo data")
    out = ""
    if opts.input != "":
        # The user specified a file that contains the input data
        # via the -i option.
        try:
            with open(opts.input, "r") as ifp:
                out = ifp.read()
        except IOError as e:
            log.fatal("input read failed: {}".format(e))
            sys.exit(1)
    else:
        # The user chose to run a git command.
        cmd = opts.gitcmd
        if cmd.replace("%%", "%") == DEFAULT_GITCMD:
            cmd = cmd.replace("%%", "%")
            if opts.cnode_label != "":
                x = cmd.rindex('"')
                cmd = (
                    cmd[:x]
                    + "%n{}|{}".format(opts.cnode_label_recid, opts.cnode_label)
                    + cmd[x:]
                )

            if opts.since != "":
                cmd += ' --since="{}"'.format(opts.since)
            if opts.until != "":
                cmd += ' --until="{}"'.format(opts.until)
            if opts.range != "":
                cmd += " {}".format(opts.range)
        else:
            # If the user specified a custom command then we
            # do not allow the user options to affect it.
            if opts.cnode_label != "":
                log.warn("-l <label> ignored when -g is specified")
            if opts.since != "":
                log.warn("--since ignored when -g is specified")
            if opts.until != "":
                log.warn("--until ignored when -g is specified")
            if opts.range != DEFAULT_RANGE:
                log.warn("--range ignored when -g is specified")

        log.info("running command: {}".format(cmd))
        st, out = runcmd(cmd)
        if st:
            log.fatal("Command failed: {}\n{}".format(cmd, out))
            sys.exit(1)
        log.info("read {:,} bytes".format(len(out)))

    if opts.keep is True:
        # The user decided to keep the generated output for
        # re-use.
        ofn = opts.outfile + ".keep"
        log.info("writing command output to {}".format(ofn))
        try:
            with open(ofn, "w") as ofp:
                ofp.write(out)
        except IOError as e:
            log.fatal("unable to write to {}: {}".format(ofn, e))
            sys.exit(1)

    return out.splitlines()


def prune_by_date(opts):
    """
    Prune by date is --since, --until or --range were specified.
    """
    if opts.since != "" or opts.until != "" or opts.range != "":
        log.info("pruning parents")
        nump = 0
        numt = 0
        for i, nd in enumerate(Node.m_list):
            np = []
            for cid in nd.m_parents:
                numt += 1
                if cid in Node.m_map:
                    np.append(cid)
                else:
                    nump += 1
            if len(np) < len(nd.m_parents):  # pruned
                Node.m_list[i].m_parents = np
                Node.m_map[nd.m_cid].m_parents = np
        log.info("pruned {:,} parent node references out of {:,}".format(nump, numt))


def prune_by_choice(opts):
    """
    Prune by --choose-branch and --choose-tag if they were specified.
    """
    if len(opts.choose_branch) > 0 or len(opts.choose_tag) > 0:
        # The algorithm is as follows:
        #     1. for each branch and tag find the associated node.
        #
        #     2. mark all nodes for deletion (m_choose=False)
        #
        #     3. walk back through graph and tag all nodes accessible
        #        from the parent link as keepers (m_choose=True).
        #        any node found that already has m_choose=True can be
        #        skipped because it was already processed by another
        #        traversal.
        #
        #     4. delete all nodes marked for deletion.
        #        iterate over all nodes, collect the delete ids in a cache
        #        reverse iterate over the cache and remove them
        #        make sure that they are removed from the list and the map
        #        just prior to delete a node, remove it from child list
        #        of its parents and from the parent list of its children.
        #        make sure that all m_idx settings are correctly updated.
        log.info("pruning graph based on choices")
        bs = {}
        ts = {}

        # initialize
        for b in opts.choose_branch:
            bs[b] = []
        for t in opts.choose_tag:
            ts[t] = []

        for idx in range(len(Node.m_list)):
            Node.m_list[idx].m_choose = False  # step 2

            # Step 1.
            nd = Node.m_list[idx]
            for b in opts.choose_branch:
                if b in nd.m_branches:
                    bs[b].append(idx)

            for t in opts.choose_tag:
                if t in nd.m_tags:
                    ts[t].append(idx)

        # Warn if any were not found.
        for b, a in sorted(bs.items()):
            if len(a) == 0:
                log.warn('--choose-branch not found: "{}"'.format(b))
        for t, a in sorted(ts.items()):
            if len(a) == 0:
                log.warn('--choose-branch not found: "{}"'.format(t))

        # At this point all of the branches and tags have been found.
        def get_parents(idx, parents):
            # Can't use recursion because large graphs may have very
            # long chains.
            # Use a breadth first expansion instead.
            # This works because git commits are always a DAG.
            stack = []
            stack.append(idx)
            while len(stack) > 0:
                idx = stack.pop()
                if idx in parents:
                    continue  # already processed

                nd = Node.m_list[idx]
                Node.m_list[idx].m_choose = True
                parents[idx] = nd.m_cid
                for pcid in nd.m_parents:
                    pidx = Node.m_map[pcid].m_idx
                    stack.append(pidx)

        parents = {}  # key=idx, val=cid
        for b, a in sorted(bs.items()):
            if len(a) > 0:
                for idx in a:
                    get_parents(idx, parents)
        for t, a in sorted(ts.items()):
            if len(a) > 0:
                for idx in a:
                    get_parents(idx, parents)

        pruning = len(Node.m_list) - len(parents)
        log.info("keeping {:,}".format(len(parents)))
        log.info("pruning {:,}".format(pruning))
        if pruning == 0:
            log.warn("nothing to prune")
            return

        # We now have all of the nodes that we want to keep.
        # We need to delete the others.
        for nd in Node.m_list[::-1]:
            if nd.m_choose == False:
                cid = nd.m_cid
                idx = nd.m_idx

                # Update the parents child lists.
                # The parent list is composed of cids.
                # Note that the child lists stored nodes.
                for pcid in nd.m_parents:
                    if pcid in Node.m_map:  # might have been deleted already
                        pnd = Node.m_map[pcid]
                        if pnd.m_choose == True:  # ignore pruned nodes (e.g. False)
                            pnd.rm_child(cid)

                # Update the child parent lists.
                # The child list is composed of nodes.
                # Note that the parent lists store cids.
                for cnd in nd.m_children:
                    if cnd.m_choose == True:  # ignore pruned nodes (e.g. False)
                        cnd.rm_parent(cid)

                # Actual deletion.
                Node.m_list = Node.m_list[:idx] + Node.m_list[idx + 1 :]
                del Node.m_map[cid]

        for i, nd in enumerate(Node.m_list):
            Node.m_list[i].m_idx = i
            Node.m_map[nd.m_cid].m_idx = i

        log.info("remaining {:,}".format(len(Node.m_list)))


def parse(opts):
    """
    Parse the node data.
    """
    log.info("loading nodes (commit data)")
    nd = None
    lines = read(opts)

    log.info("parsing read data")
    for line in lines:
        line = line.strip()
        if line.find("|Record:|") >= 0:
            flds = line.split("|")
            assert flds[1] == "Record:"
            cid = flds[2]  # Commit id.
            pids = flds[3].split()  # parent ids
            tags = []
            branches = []
            refs = flds[4].strip()
            try:
                dts = dateutil.parser.parse(flds[5])
            except:
                log.fatal("unrecognized date format: {}\n\tline: {}".format(flds[5], line))
                sys.exit(1)
            if len(refs):
                # branches and tags
                if refs[0] == "(" and refs[-1] == ")":
                    refs = refs[1:-1]
                for fld in refs.split(","):
                    fld = fld.strip()
                    if "tag: " in fld:
                        tags.append(fld)
                    else:
                        ref = fld
                        if " -> " in fld:
                            ref = fld.split(" -> ")[1]
                        branches.append(ref)
            nd = Node(cid, pids, branches, tags, dts)

        if opts.define_var is not None:
            # The user defined one or more variables.
            # Scan each line to see if the variable
            # specification exists.
            for p in opts.define_var:
                var = p[0]
                reg = p[1]
                m = re.search(reg, line)
                if m:
                    # A variable was found.
                    val = m.group(1)

                    # Set the value on the node.
                    idx = nd.m_idx
                    if var not in Node.m_list[idx].m_vars:
                        Node.m_list[idx].m_vars[var] = []
                    Node.m_list[idx].m_vars[var].append(val)

                    # keep track of which nodes have this defined.
                    if var not in Node.m_vars_usage:
                        Node.m_vars_usage[var] = []
                    Node.m_vars_usage[var].append(nd.m_cid)

        if opts.cnode_label_recid in line:
            # Add the additional commit node label data into the node.
            th = opts.cnode_label_maxwidth
            flds = line.split("|")
            idx = nd.m_idx

            def setval(idx, th, val):
                if th > 0:
                    val = val[:th]
                val = val.replace('"', '\\"')
                Node.m_list[idx].m_extra.append(val)

            # Update the field values.
            for fld in flds[1:]:  # skip the record field
                # We have the list of fields but these are not, necessarily
                # the same as the variables.
                # Example: @CHID@
                # Example: FOO@CHID@BAR
                # Example: @CHID@ + %s | next field |
                # Get the values for each variable and substitute them.
                found = False
                if opts.define_var is not None:
                    for p in opts.define_var:
                        var = p[0]
                        if var in fld:
                            found = True
                            # The value is defined on this node.
                            # If it isn't we just ignore it.
                            if var in Node.m_list[idx].m_vars:
                                vals = Node.m_list[idx].m_vars[var]
                                if len(vals) == 1:
                                    fld = fld.replace(var, vals[0])
                                    setval(idx, th, fld)
                                else:
                                    # This is hard because there may be
                                    # multiple variables that are vectors
                                    # of different sizes, punt for now.
                                    fld = fld.replace(var, "{}".format(vals))
                                    setval(idx, th, fld)
                if not found:
                    setval(idx, th, fld)

    if len(Node.m_list) == 0:
        log.fatal("no records found")
        sys.exit(1)

    prune_by_date(opts)
    prune_by_choice(opts)

    # Update the child list for each node by looking at the parents.
    # This helps us identify merge nodes.
    log.info("updating children")
    num_edges = 0
    for nd in Node.m_list:
        for p in nd.m_parents:
            num_edges += 1
            Node.m_map[p].m_children.append(nd)

    # Summary of initial read.
    log.info("found {:,} commit nodes".format(len(Node.m_list)))
    log.info("found {:,} commit edges".format(num_edges))
    for var in Node.m_vars_usage:
        log.info(
            'found {:,} nodes with values for variable "{}"'.format(
                len(Node.m_vars_usage[var]), var
            )
        )

    # Squash nodes.
    if opts.squash:
        log.info("squashing chains")
        Node.squash()

    # Create the bydate list to enable ranking using invisible
    # constraints.
    log.info("sorting by date")
    Node.m_list_bydate = [nd.m_cid for nd in Node.m_list]
    Node.m_list_bydate.sort(key=lambda x: Node.m_map[x].m_dts)


def gendot(opts) -> str:
    """
    Generate a test graph.
    """
    # Keep track of the node information so
    # that it can be reported at the end.
    summary = {
        "num_graph_commit_nodes": 0,
        "num_graph_merge_nodes": 0,
        "num_graph_squash_nodes": 0,
        "total_graph_commit_nodes": 0,  # sum of commit, merge and squash nodes
        "total_commits": 0,
    }  # total nodes with no squashing

    dot = "digraph G {\n"
    for v in opts.dot_option:
        if len(opts.font_size) and "fontsize=" in v:
            v = re.sub(r"(fontsize=)[^,]+,", r'\1"' + opts.font_size + r'",', v)
        if len(opts.font_name) and "fontsize=" in v:
            v = re.sub(
                r"(fontsize=[^,]+),", r'\1, fontname="' + opts.font_name + r'",', v
            )
        dot += "   {}".format(v)
        if v[-1] != ";":
            dot += ";"
        dot += "\n"

    dot += "\n"
    dot += "   // label cnode, mnode and snodes\n"
    for nd in Node.m_list:
        if opts.squash and nd.is_squashed():
            continue
        if nd.is_merge_node():
            label = "\\n".join(nd.m_extra)
            attrs = opts.mnode.format(label=label)
            dot += '   "{}" {};\n'.format(nd.m_cid, attrs)
            summary["num_graph_merge_nodes"] += 1
            summary["total_graph_commit_nodes"] += 1
            summary["total_commits"] += 1
        elif nd.is_squashed_head() or nd.is_squashed_tail():
            label = "\\n".join(nd.m_extra)
            attrs = opts.snode.format(label=label)
            dot += '   "{}" {};\n'.format(nd.m_cid, attrs)
            summary["num_graph_squash_nodes"] += 1
            summary["total_graph_commit_nodes"] += 1
        else:
            label = "\\n".join(nd.m_extra)
            attrs = opts.cnode.format(label=label)
            dot += '   "{}" {};\n'.format(nd.m_cid, attrs)
            summary["num_graph_commit_nodes"] += 1
            summary["total_graph_commit_nodes"] += 1
            summary["total_commits"] += 1

    log.info("defining edges")
    dot += "\n"
    dot += "   // edges\n"
    for nd in Node.m_list:
        if nd.is_squashed():
            continue
        elif nd.is_squashed_tail():
            continue

        if nd.is_squashed_head():
            # Special handling for squashed head nodes, create
            # a squash edge between the head and tail.
            attrs = opts.sedge.format(label=nd.m_chain_size)
            dot += '   "{}" -> "{}" {};\n'.format(nd.m_cid, nd.m_chain_tail.m_cid, attrs)
            summary["total_commits"] += nd.m_chain_size

        # Create the edges to the parents.
        for pid in nd.m_parents:
            attrs = ""
            if nd.is_merge_node():
                if len(opts.mnode_pedge) > 0:
                    attrs = opts.mnode_pedge.format(
                        label="{} to {}".format(nd.m_cid, pid)
                    )
                dot += '   "{}" -> "{}" {};\n'.format(pid, nd.m_cid, attrs)
            else:
                if len(opts.cnode_pedge) > 0:
                    attrs = opts.cnode_pedge.format(
                        label="{} to {}".format(nd.m_cid, pid)
                    )
                dot += '   "{}" -> "{}" {};\n'.format(pid, nd.m_cid, attrs)

    # Annote the tags and branches for each node.
    # Can't use subgraphs because rankdir is not
    # supported.
    log.info("annotating branches and tags")
    dot += "\n"
    dot += "   // annotate branches and tags\n"
    first = True
    for idx, nd in enumerate(Node.m_list):
        # technically this is redundant because squashed nodes, by
        # definition, do not have branches or tag refs.
        if nd.is_squashed():
            continue
        if len(nd.m_branches) > 0 or len(nd.m_tags) > 0:
            torank = [nd.m_cid]
            if first:
                first = False
            else:
                dot += "\n"

            if len(nd.m_tags) > 0:
                if opts.crunch:
                    # Create the node name.
                    tid = "tid-{:>08}".format(idx)
                    label = "\\n".join(nd.m_tags)
                    attrs = opts.tnode.format(label=label)
                    dot += '   "{}" {};\n'.format(tid, attrs)
                    torank += [tid]

                    # Write the connecting edge.
                    dot += '   "{}" -> "{}"'.format(tid, nd.m_cid)
                else:
                    torank += nd.m_tags
                    for t in nd.m_tags:
                        # Tag node definitions.
                        attrs = opts.tnode.format(label=t)
                        dot += '   "{}+{}" {};\n'.format(nd.m_cid, t, attrs)

                    tl = nd.m_tags
                    dot += '   "{}+{}"'.format(nd.m_cid, tl[0])
                    for t in tl[1:]:
                        dot += ' -> "{}+{}"'.format(nd.m_cid, t)
                    dot += ' -> "{}"'.format(nd.m_cid)

                attrs = opts.tedge.format(label=nd.m_cid)
                dot += " {};\n".format(attrs)

            if len(nd.m_branches) > 0:
                if opts.crunch:
                    # Create the node name.
                    bid = "bid-{:>08}".format(idx)
                    label = "\\n".join(nd.m_branches)
                    attrs = opts.bnode.format(label=label)
                    dot += '   "{}" {};\n'.format(bid, attrs)
                    torank += [bid]

                    # Write the connecting edge.
                    dot += '   "{}" -> "{}"'.format(nd.m_cid, bid)
                else:
                    torank += nd.m_branches
                    for b in nd.m_branches:
                        # Branch node definitions.
                        attrs = opts.bnode.format(label=b)
                        dot += '   "{}+{}" {};\n'.format(nd.m_cid, b, attrs)

                    dot += '   "{}"'.format(nd.m_cid)
                    for b in nd.m_branches[::-1]:
                        dot += ' -> "{}+{}"'.format(nd.m_cid, b)

                attrs = opts.bedge.format(label=nd.m_cid)
                dot += " {};\n".format(attrs)

            # Make sure that they line up by putting them in the same rank.
            dot += '   {{rank=same; "{}"'.format(torank[0])
            for cid in torank[1:]:
                if opts.crunch:
                    dot += '; "{}"'.format(cid)
                else:
                    dot += '; "{}+{}"'.format(nd.m_cid, cid)
            dot += "};\n"

    # Align nodes by commit date.
    if opts.align_by_date != "none":
        log.info("align by {}".format(opts.align_by_date))
        dot += "\n"
        dot += "   // rank by date using invisible constraints between groups\n"
        lnd = Node.m_map[Node.m_list_bydate[0]]

        attrs = ["year", "month", "day", "hour", "minute", "second"]
        for cid in Node.m_list_bydate:
            nd = Node.m_map[cid]
            if nd.is_squashed():
                continue

            for attr in attrs:
                v1 = getattr(nd.m_dts, attr)
                v2 = getattr(lnd.m_dts, attr)
                if v1 < v2:
                    # Add an invisible constraint to guarantee that the later node
                    # appears somewhere to the right.
                    log.info(
                        "aligning {} {} to the left of {} {}".format(
                            lnd.m_cid, lnd.m_dts, nd.m_cid, nd.m_dts
                        )
                    )
                    dot += '   "{}" -> "{}" [style=invis];\n'.format(lnd.m_cid, nd.m_cid)

                elif v1 > v2:
                    break
                if attr == opts.align_by_date:
                    continue

            if lnd.m_dts < nd.m_dts:
                lnd = nd

    # Output the graph label.
    if opts.graph_label is not None:
        log.info("generate graph label")
        dot += "\n"
        dot += "   // graph label\n"
        dot += "   {}".format(opts.graph_label)

        if opts.graph_label[-1] != ";":
            dot += ";"
        dot += "\n"

    dot += "}\n"

    # Output the summary data.
    for k in sorted(summary, key=str.lower):
        v = summary[k]
        dot += "// summary:{} {}\n".format(k, v)
    return dot


def gengraph(opts, dot: str, fmt: Optional[str]) -> bytes:
    """
    Generate the graph file using dot with -O option.
    """
    log.info("generating {}".format(fmt))
    graphs = pydot.graph_from_dot_data(dot)
    graph = graphs[0]
    if fmt == "svg":
        return graph.create_svg()
    return graph.create_png()
