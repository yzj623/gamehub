from __future__ import annotations

import os
from typing import Iterable

import pymysql

from app import create_app
from config import Config


def _read_statements(path: str) -> Iterable[str]:
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
    with connection.cursor() as cursor:
        for stmt in _read_statements(path):
            # Use multi=True to handle statements containing semicolons
            # (e.g. CREATE PROCEDURE / FUNCTION / TRIGGER with DELIMITER)
            for result in cursor.execute(stmt, multi=True):
                if result.with_rows:
                    result.fetchall()
    connection.commit()


def _ensure_database() -> None:
    """Auto-create database if it doesn't exist, then import SQL files if tables are empty."""
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
                cursor.execute(f"CREATE DATABASE `{Config.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                print(f"[start_server] 数据库 '{Config.DB_NAME}' 创建成功！")
            else:
                print(f"[start_server] 数据库 '{Config.DB_NAME}' 已存在。")
    finally:
        conn_no_db.close()

    # Step 2: Connect to the database and check if tables exist
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
                print("[start_server] 数据库为空，正在导入 phase1_schema.sql ...")
                _execute_sql_file(conn, "phase1_schema.sql")
                print("[start_server] phase1_schema.sql 导入完成！")

                # Import seed data if SEED_DATA env var is set
                if os.environ.get("SEED_DATA") == "1":
                    seed_file = "phase4_seed.sql"
                    if os.path.exists(seed_file):
                        print(f"[start_server] 正在导入 {seed_file} ...")
                        _execute_sql_file(conn, seed_file)
                        print(f"[start_server] {seed_file} 导入完成！")

                # Import friend chat feature if file exists
                friend_file = "phase5_friend_chat.sql"
                if os.path.exists(friend_file):
                    print(f"[start_server] 正在导入 {friend_file} ...")
                    _execute_sql_file(conn, friend_file)
                    print(f"[start_server] {friend_file} 导入完成！")
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
