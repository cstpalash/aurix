"""
Main entry point for Aurix platform.
"""

import argparse
import sys


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Aurix - Autonomous Human-in-the-Loop Removal Platform"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Server command
    server_parser = subparsers.add_parser("server", help="Run the API server")
    server_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to",
    )
    server_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload",
    )
    
    # Review command
    review_parser = subparsers.add_parser("review", help="Review a pull request")
    review_parser.add_argument("repo", help="Repository (owner/repo)")
    review_parser.add_argument("pr_number", type=int, help="Pull request number")
    
    # Pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="Run SDLC pipeline")
    pipeline_parser.add_argument("repo", help="Repository name")
    pipeline_parser.add_argument(
        "--branch",
        default="main",
        help="Branch to deploy",
    )
    pipeline_parser.add_argument(
        "--environment",
        default="staging",
        choices=["development", "staging", "production"],
        help="Target environment",
    )
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check graduation status")
    status_parser.add_argument("repo", help="Repository (owner/repo)")
    
    args = parser.parse_args()
    
    if args.command == "server":
        import uvicorn
        uvicorn.run(
            "aurix.api.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    
    elif args.command == "review":
        import asyncio
        from aurix.cli.commands import review_pr
        asyncio.run(review_pr(args.repo, args.pr_number))
    
    elif args.command == "pipeline":
        import asyncio
        from aurix.cli.commands import run_pipeline
        asyncio.run(run_pipeline(args.repo, args.branch, args.environment))
    
    elif args.command == "status":
        from aurix.cli.commands import check_status
        check_status(args.repo)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
