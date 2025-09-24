import argparse

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="OpenHands Agent Server App")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        dest="reload",
        default=False,
        action="store_true",
        help="Enable auto-reload (disabled by default)",
    )

    args = parser.parse_args()

    print(f"🚀 Starting OpenHands Agent Server on {args.host}:{args.port}")
    print(f"📖 API docs will be available at http://{args.host}:{args.port}/docs")
    print(f"🔄 Auto-reload: {'enabled' if args.reload else 'disabled'}")
    print()

    uvicorn.run(
        "openhands.agent_server.api:api",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_excludes=["workspace"],
    )


if __name__ == "__main__":
    main()
