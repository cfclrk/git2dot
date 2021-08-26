from git2dot import cli

def test_args():
    parser = cli.arg_parser()
    args = parser.parse_args()
    print(args)
