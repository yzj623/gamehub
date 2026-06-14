from __future__ import annotations

import os
from typing import Iterable

import pymysql

from app import create_app
from config import Config


def _read_statements(path: str) -> Iterable[str]:
    """Read SQL statements from a file, handling DELIMITER statements."""
    delimiter = ";"
    buffer: list[str] = []

    with open(path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("--"):
                continue
            if line.upper().startswith("DELIMITER"):
                delimiter = line.split()[1]
                continue
            buffer.append(raw_line.rstrip("\n"))
            joined = "\n".join(buffer).strip()
            if joined.endswith(delimiter):
                stmt = joined[: -len(delimiter)].strip()
                if stmt:
                    yield stmt
                buffer = []

    leftover = "\n".join(buffer).strip()
    if leftover:
        yield leftover


def _execute_sql_file(connection: pymysql.Connection, path: str) -> None:
    """Execute all SQL statements from a file."""
    with connection.cursor() as cursor:
        for stmt in _read_statements(path):
            stripped = stmt.strip().upper()
            if stripped.startswith("USE ") or stripped.startswith("CREATE DATABASE"):
                continue
            try:
                cursor.execute(stmt)
            except Exception as e:
                print(f"[start_server] 跳过语句（可能已存在）: {e}")
    connection.commit()


def _ensure_database() -> None:
    """Auto-create database if it doesn't exist, then import schema.sql."""
    # Step 1: Connect without database to check/create it
    conn_no_db = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn_no_db.cursor() as cursor:
            cursor.execute(
                f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s",
                (Config.DB_NAME,),
            )
            exists = cursor.fetchone()
            if not exists:
                print(f"[start_server] 数据库 '{Config.DB_NAME}' 不存在，正在创建...")
                cursor.execute(
                    f"CREATE DATABASE `{Config.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                print(f"[start_server] 数据库 '{Config.DB_NAME}' 创建成功！")
            else:
                print(f"[start_server] 数据库 '{Config.DB_NAME}' 已存在。")
    finally:
        conn_no_db.close()

    # Step 2: Connect to the database and import schema
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            if not tables:
                print("[start_server] 数据库为空，正在导入 schema.sql ...")
                _execute_sql_file(conn, "schema.sql")
                print("[start_server] schema.sql 导入完成！")

                # Import seed data if SEED_DATA env var is set
                if os.environ.get("SEED_DATA") == "1":
                    seed_file = "phase4_seed.sql"
                    if os.path.exists(seed_file):
                        print(f"[start_server] 正在导入 {seed_file} ...")
                        _execute_sql_file(conn, seed_file)
                        print(f"[start_server] {seed_file} 导入完成！")
            else:
                print(f"[start_server] 数据库已有 {len(tables)} 张表，跳过导入。")
    finally:
        conn.close()


def main() -> None:
    _ensure_database()
    app = create_app()
    port = int(os.environ.get("FLASK_PORT", "5000"))
    print(f"[start_server] 启动服务，访问 http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()
