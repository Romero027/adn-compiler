import argparse
import os
import sys
from pathlib import Path

from rich.columns import Columns
from rich.console import Console

# set up $PYTHONPATH and environment variables
sys.path.append(str(Path(__file__).parent.parent.absolute()))
sys.path.append(str(Path(__file__).parent.absolute()))
os.environ["PHOENIX_DIR"] = os.path.join(os.getenv("HOME"), "phoenix")

from compiler import graph_base_dir
from compiler.element import gen_code
from compiler.graph.backend import scriptgen
from compiler.graph.frontend import GCParser
from compiler.graph.logger import IR_LOG, init_logging
from compiler.graph.pseudo_element_compiler import pseudo_compile

console = Console()
gir_summary = dict()


def compile_impl(spec: str, gen_dir: str, backend: str):
    engine_name = spec.split("/")[-1].split(".")[0]
    gen_dir = os.path.join(gen_dir, f"{engine_name}_{backend}")
    os.system(f"mkdir -p {gen_dir}")
    gen_code(engine_name, engine_name, gen_dir, backend, "receiver")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s", "--spec_path", help="User specification file", type=str, required=True
    )
    parser.add_argument(
        "--app",
        type=str,
        required=True,
        choices=["rpc_echo", "hotel", "rpc_echo_local", "hotel_local"],
    )
    parser.add_argument("-v", "--verbose", help="Print Debug info", action="store_true")
    parser.add_argument("--pseudo_property", action="store_true")
    parser.add_argument("--pseudo_impl", action="store_true")
    parser.add_argument("-b", "--backend", type=str, required=True, choices=["mrpc"])
    parser.add_argument(
        "--mrpc_dir",
        type=str,
        default=os.path.join(os.getenv("HOME"), "phoenix/experimental/mrpc"),
    )
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    init_logging(args.debug)

    if args.dry_run:
        os.environ["DRY_RUN"] = "1"

    parser = GCParser()
    graphirs = parser.parse(args.spec_path)

    if args.verbose:
        for gir in graphirs.values():
            if gir.name not in gir_summary:
                gir_summary[gir.name] = {"pre-optimized": [], "post-optimized": []}
            gir_summary[gir.name]["pre-optimized"] = gir.to_rich()

    compiled_spec = set()
    for gir in graphirs.values():
        gir.optimize(args.pseudo_property)

    if not args.dry_run:
        for gir in graphirs.values():
            for element in gir.elements["req_client"] + gir.elements["req_server"]:
                for spec in element.spec:
                    if spec not in compiled_spec:
                        if args.pseudo_impl:
                            pseudo_compile(
                                spec, os.path.join(graph_base_dir, "gen"), args.backend
                            )
                        else:
                            compile_impl(
                                spec, os.path.join(graph_base_dir, "gen"), args.backend
                            )
                    compiled_spec.add(spec)
        scriptgen(graphirs, args.backend, args.app)

    if args.verbose:
        IR_LOG.info("GraphIR summary:")
        for gir in graphirs.values():
            gir_summary[gir.name]["post-optimized"] = gir.to_rich()
            gir_summary[gir.name]["property"] = {}
            for element in gir.elements["req_client"] + gir.elements["req_server"]:
                gir_summary[gir.name]["property"][element.deploy_name] = element.prop
        for gname, summary in gir_summary.items():
            console.print()
            console.print(gname, style="underline bold italic")
            console.print(Columns(["\n :snail: :\n"] + summary["pre-optimized"]))
            console.print(Columns(["\n :rocket: :\n"] + summary["post-optimized"]))
            if args.debug:
                console.print("Properties:")
                for ename, prop in summary["property"].items():
                    console.print(f"{ename}: {prop['request']}")
