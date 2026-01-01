#!/usr/bin/env python3
import argparse
from genlib.catalog.cli import catalog_cli
from genlib.compose import compose_cli
from genlib.stack.cli import stack_cli
from genlib.agents.cli import agent_cli
from genlib.stack.commands import init_cmd
from genlib.engines.remote import remote_cli


def main():
    parser = argparse.ArgumentParser(
        prog="genlib",
        description="Generative model & prompt stack library CLI"
    )
    subparsers = parser.add_subparsers(dest="domain", required=True)

    # p_init = subparsers.add_parser("init", help="Initialize GenLib workspace")
    # p_init.add_argument(
    #     "--engine",
    #     default="forge",
    #     choices=["forge", "none"],
    #     help="Default execution engine",
    # )
    # p_init.add_argument(
    #     "--force",
    #     action="store_true",
    #     help="Overwrite existing CMF",
    # )
    # p_init.set_defaults(func=init_cmd)

    # stack_cli(p_init)


    catalog_parser = subparsers.add_parser("catalog", help="Manage local model catalog")
    catalog_cli(catalog_parser)
    
    remote_parser = subparsers.add_parser("remote", help="Search civit AI for models")
    remote_cli(remote_parser)

    compose_parser = subparsers.add_parser("compose", help="Compose prompt stacks")
    compose_cli(compose_parser)

    stack_parser = subparsers.add_parser("stack", help="Create, resolve, and run prompt stacks")
    stack_cli(stack_parser)

    agent_parser = subparsers.add_parser("agent", help="Agent: natural language -> plan/run")
    agent_cli(agent_parser)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
