#!/bin/bash
#
# Create two branches and two tags.
#

# ================================================================
# Includes
# ================================================================
Location="$(cd $(dirname $0) && pwd)"
source $Location/test-utils.sh

# ================================================================
# Create the repo.
# ================================================================
if (( Keep )) ; then
    runcmd git init

    echo 'A' >$Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'master - first'"

    echo 'B' >>$Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'master - second'"

    # tag the basis for all of the branches
    runcmd git tag -a 'v1.0' -m "'Initial version.'"
    runcmd git tag -a 'v1.0a' -m "'Another version.'"

    runcmd git checkout -b branchX1
    runcmd git checkout master
    runcmd git checkout -b branchX2

    runcmd git checkout master
    runcmd git checkout -b branchA
    runcmd echo 'C' '>>' $Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'branchA - first'"

    runcmd echo 'D' '>>' $Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'branchA - second'"

    runcmd git checkout master
    runcmd git checkout -b branchB
    runcmd echo 'E' '>>' $Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'branchB - first'"

    runcmd echo 'F' '>>' $Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'branchB - second'"

    runcmd echo 'G' '>>' $Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'branchB - third'"

    runcmd echo 'H' '>>' $Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'branchB - fourth'"

    runcmd echo 'I' '>>' $Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'branchB - fifth'"

    runcmd echo 'J' '>>' $Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'branchB - sixth'"

    runcmd echo 'K' '>>' $Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'branchB - seventh'"

    runcmd git checkout master
    runcmd echo 'L' '>>' $Name.txt
    runcmd git add $Name.txt
    runcmd git commit -m "'master - third'"
fi

# ================================================================
# Report.
# ================================================================
echo ""
Purpose="3 branches, squash enabled, tags and branches"
runcmd git2dot \
       $KeepOpt \
       -v \
       -v \
       -w 19 \
       -l "'%s|%ci'" \
       -L "'graph[label=<<table border=\"0\"><tr><td border=\"1\" align=\"left\" balign=\"left\" bgcolor=\"lightyellow\"><font face=\"courier\" point-size=\"9\">Test:    $Name<br/>Purpose: $Purpose<br/>Dir:     $(pwd)<br/>Date:    $(date)</font></td></tr></table>>]'" \
       -s \
       --png \
       --svg \
       -o $Name.dot

Finish
info 'done'
