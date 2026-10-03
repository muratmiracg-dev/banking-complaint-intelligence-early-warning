import argparse
from .config import ROOT


def main():
    parser = argparse.ArgumentParser(description='CFPB banking complaint intelligence workbench')
    commands = parser.add_subparsers(dest='command',required=True)
    commands.add_parser('fetch',help='Download official metadata and historical narrative archives (~290 MB)')
    build = commands.add_parser('build',help='Train, evaluate and regenerate all analytical artifacts')
    build.add_argument('--input',default=str(ROOT/'data/processed/cohort.csv'))
    server = commands.add_parser('serve',help='Open local interactive workbench')
    server.add_argument('--port',type=int,default=8765)
    commands.add_parser('validate',help='Verify committed artifact invariants')
    args = parser.parse_args()
    if args.command == 'fetch':
        from .data import acquire
        acquire()
    elif args.command == 'build':
        from .pipeline import build
        build(args.input)
    elif args.command == 'serve':
        from .server import serve
        serve(args.port)
    else:
        from .validate import validate_artifacts
        validate_artifacts()


if __name__ == '__main__':
    main()
