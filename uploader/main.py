import argparse
import os

from tqdm import tqdm

import queue_db
import scanner
from config import load_config
from structured_logger import StructuredLogger
from uploader import Uploader


def cmd_run(args):
    config = load_config(allow_insecure_local=args.allow_insecure_local)
    if args.api_url:
        config.api_url = args.api_url.rstrip("/")

    logger = StructuredLogger()
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploader_state.db")

    print(f"Varrendo {args.root} ...")
    with queue_db.get_connection(db_path) as conn:
        new_count = 0
        for abs_path, _relative_path, file_hash in scanner.scan_root(args.root):
            if queue_db.insert_if_new(conn, abs_path, file_hash):
                new_count += 1
        print(f"{new_count} arquivo(s) novo(s) adicionado(s) à fila.")

        items = queue_db.get_eligible_items(conn, config.max_retries)
        print(f"{len(items)} item(ns) elegível(is) para processar nesta execução.")

        uploader = Uploader(config, args.root, logger)
        try:
            for item in tqdm(items, desc="Processando fila", unit="arquivo"):
                uploader.process_item(conn, item)
                conn.commit()
        finally:
            uploader.close()

    _print_report(db_path)


def cmd_report(args):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploader_state.db")
    _print_report(db_path)


def _print_report(db_path: str):
    with queue_db.get_connection(db_path) as conn:
        counts = queue_db.status_counts(conn)
        print("\n--- Resumo ---")
        for status, count in counts.items():
            print(f"  {status}: {count}")

        falhas = queue_db.falhas_permanentes(conn)
        if falhas:
            print(f"\n--- Falhas permanentes ({len(falhas)}) ---")
            for item in falhas:
                print(f"  {item.caminho_absoluto}")
                print(f"    -> {item.mensagem_erro}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Uploader local para o agente RAG")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Varre e envia a fila (padrão)")
    run_parser.add_argument("--root", required=True, help="Pasta raiz a varrer recursivamente")
    run_parser.add_argument("--api-url", help="Sobrescreve API_URL do .env")
    run_parser.add_argument(
        "--allow-insecure-local", action="store_true",
        help="Permite http:// em vez de https:// — só para teste local sem internet",
    )
    run_parser.set_defaults(func=cmd_run)

    report_parser = subparsers.add_parser("report", help="Mostra o resumo de status sem processar nada")
    report_parser.set_defaults(func=cmd_report)

    args = parser.parse_args()

    # Compatibilidade com a forma descrita no plano: `python main.py --root ... [--report]`
    if args.command is None:
        fallback_parser = argparse.ArgumentParser()
        fallback_parser.add_argument("--root")
        fallback_parser.add_argument("--api-url")
        fallback_parser.add_argument("--allow-insecure-local", action="store_true")
        fallback_parser.add_argument("--report", action="store_true")
        fallback_args = fallback_parser.parse_args()

        if fallback_args.report:
            cmd_report(fallback_args)
        elif fallback_args.root:
            cmd_run(fallback_args)
        else:
            parser.print_help()
    else:
        args.func(args)
