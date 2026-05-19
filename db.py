from __future__ import annotations

import queue
from contextlib import contextmanager
from typing import Iterator

import pymysql
from pymysql import err as pymysql_err

from config import Config


class DBPool:
    def __init__(self, size: int) -> None:
        self._pool: queue.Queue[pymysql.connections.Connection] = queue.Queue(maxsize=size)
        for _ in range(size):
            self._pool.put(self._create_conn())

    def _create_conn(self) -> pymysql.connections.Connection:
        try:
            return pymysql.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                charset="utf8mb4",
            )
        except pymysql_err.OperationalError as exc:
            if exc.args and exc.args[0] == 1049:
                self._ensure_database()
                return pymysql.connect(
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    database=Config.DB_NAME,
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=False,
                    charset="utf8mb4",
                )
            raise

    def _ensure_database(self) -> None:
        conn = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            autocommit=True,
            charset="utf8mb4",
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "CREATE DATABASE IF NOT EXISTS steam_platform "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
        finally:
            conn.close()

    @contextmanager
    def get_conn(self) -> Iterator[pymysql.connections.Connection]:
        conn = self._pool.get()
        try:
            yield conn
        finally:
            try:
                conn.ping(reconnect=True)
            except pymysql.MySQLError:
                conn = self._create_conn()
            self._pool.put(conn)


pool = DBPool(Config.POOL_SIZE)


def fetch_all(sql: str, params: tuple | None = None) -> list[dict]:
    with pool.get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            result = cursor.fetchall()
        conn.commit()
    return result


def fetch_one(sql: str, params: tuple | None = None) -> dict | None:
    with pool.get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            result = cursor.fetchone()
        conn.commit()
    return result



def execute(sql: str, params: tuple | None = None) -> int:
    with pool.get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            last_id = cursor.lastrowid
            rowcount = cursor.rowcount
        conn.commit()
    return last_id if last_id else rowcount




def call_proc(name: str, params: tuple | None = None) -> list[dict]:
    with pool.get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.callproc(name, params or ())
            result = cursor.fetchall()
        conn.commit()
    return result
