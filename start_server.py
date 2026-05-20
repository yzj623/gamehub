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
            stripped = stmt.strip().upper()
            if stripped.startswith("USE ") or stripped.startswith("CREATE DATABASE"):
                continue
            try:
                cursor.execute(stmt)
            except Exception as e:
                print(f"[start_server] 跳过语句（可能已存在）: {e}")
    connection.commit()


def _ensure_procs(connection: pymysql.Connection) -> None:
    """Create stored procedures, functions, and triggers using raw SQL.
    This avoids DELIMITER issues that pymysql cannot handle."""
    with connection.cursor() as cursor:
        # Drop existing objects
        cursor.execute("DROP PROCEDURE IF EXISTS GetTopRatedGames")
        cursor.execute("DROP PROCEDURE IF EXISTS GetGamesByPrice")
        cursor.execute("DROP PROCEDURE IF EXISTS GetTopSellingGames")
        cursor.execute("DROP PROCEDURE IF EXISTS PurchaseGameTransaction")
        cursor.execute("DROP FUNCTION IF EXISTS GetSteamStatus")
        cursor.execute("DROP TRIGGER IF EXISTS After_Review_Insert")
        connection.commit()

        # Create GetTopRatedGames
        cursor.execute("""
            CREATE PROCEDURE GetTopRatedGames()
            BEGIN
                SELECT
                    g.game_id,
                    g.title,
                    g.price,
                    g.avg_rating,
                    g.review_count,
                    g.cover_path
                FROM Games g
                ORDER BY g.avg_rating DESC, g.review_count DESC
                LIMIT 10;
            END
        """)

        # Create GetGamesByPrice
        cursor.execute("""
            CREATE PROCEDURE GetGamesByPrice(IN p_desc TINYINT)
            BEGIN
                IF p_desc = 1 THEN
                    SELECT
                        g.game_id, g.title, g.price,
                        g.avg_rating, g.review_count, g.cover_path
                    FROM Games g
                    ORDER BY g.price DESC
                    LIMIT 10;
                ELSE
                    SELECT
                        g.game_id, g.title, g.price,
                        g.avg_rating, g.review_count, g.cover_path
                    FROM Games g
                    ORDER BY g.price ASC
                    LIMIT 10;
                END IF;
            END
        """)

        # Create GetSteamStatus function
        cursor.execute("""
            CREATE FUNCTION GetSteamStatus(p_game_id INT)
            RETURNS VARCHAR(20)
            DETERMINISTIC
            BEGIN
                DECLARE v_avg DECIMAL(3,2);
                SELECT avg_rating INTO v_avg FROM Games WHERE game_id = p_game_id;
                IF v_avg IS NULL THEN
                    RETURN '暂无评价';
                ELSEIF v_avg >= 4.5 THEN
                    RETURN '好评如潮';
                ELSEIF v_avg >= 3.0 THEN
                    RETURN '褒贬不一';
                ELSE
                    RETURN '差评如潮';
                END IF;
            END
        """)

        # Create After_Review_Insert trigger
        cursor.execute("""
            CREATE TRIGGER After_Review_Insert
            AFTER INSERT ON Reviews
            FOR EACH ROW
            BEGIN
                UPDATE Games g
                SET
                    g.avg_rating = (
                        SELECT ROUND(AVG(r.rating), 2)
                        FROM Reviews r
                        WHERE r.game_id = NEW.game_id
                    ),
                    g.review_count = (
                        SELECT COUNT(*)
                        FROM Reviews r
                        WHERE r.game_id = NEW.game_id
                    )
                WHERE g.game_id = NEW.game_id;
            END
        """)

        # Create GetTopSellingGames
        cursor.execute("""
            CREATE PROCEDURE GetTopSellingGames()
            BEGIN
                SELECT
                    g.game_id,
                    g.title,
                    g.price,
                    g.avg_rating,
                    g.review_count,
                    g.cover_path,
                    COUNT(o.order_id) AS sales_count
                FROM Games g
                LEFT JOIN Orders o ON o.game_id = g.game_id
                GROUP BY g.game_id, g.title, g.price, g.avg_rating, g.review_count, g.cover_path
                ORDER BY sales_count DESC, g.avg_rating DESC
                LIMIT 10;
            END
        """)

        # Create PurchaseGameTransaction
        cursor.execute("""
            CREATE PROCEDURE PurchaseGameTransaction(IN p_user_id INT, IN p_game_id INT)
            BEGIN
                DECLARE v_price DECIMAL(10,2);
                DECLARE v_balance DECIMAL(10,2);
                DECLARE v_publisher_id INT;
                DECLARE v_exists INT DEFAULT 0;
                DECLARE EXIT HANDLER FOR SQLEXCEPTION
                BEGIN
                    ROLLBACK;
                    RESIGNAL;
                END;
                START TRANSACTION;
                SELECT price, publisher_id INTO v_price, v_publisher_id
                FROM Games WHERE game_id = p_game_id FOR UPDATE;
                IF v_price IS NULL THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Game not found';
                END IF;
                SELECT balance INTO v_balance
                FROM Users WHERE user_id = p_user_id FOR UPDATE;
                IF v_balance IS NULL THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'User not found';
                END IF;
                SELECT COUNT(*) INTO v_exists
                FROM Orders WHERE user_id = p_user_id AND game_id = p_game_id;
                IF v_exists > 0 THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Already purchased';
                END IF;
                IF v_balance < v_price THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Insufficient balance';
                END IF;
                UPDATE Users SET balance = balance - v_price WHERE user_id = p_user_id;
                UPDATE Users SET balance = balance + v_price WHERE user_id = v_publisher_id;
                INSERT INTO Orders(user_id, game_id, price) VALUES (p_user_id, p_game_id, v_price);
                COMMIT;
            END
        """)

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
                # Ensure FriendMessages table exists
                with conn.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS FriendMessages (
                            msg_id INT AUTO_INCREMENT PRIMARY KEY,
                            sender_id INT NOT NULL,
                            receiver_id INT NOT NULL,
                            content TEXT,
                            image_path VARCHAR(500),
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (sender_id) REFERENCES Users(user_id),
                            FOREIGN KEY (receiver_id) REFERENCES Users(user_id)
                        )
                    """)
                    print("[start_server] FriendMessages 表已确认存在。")

            # Always re-create stored procedures, functions, and triggers
            # (in case they were missing from a previous import)
            print("[start_server] 正在重新创建存储过程/函数/触发器...")
            _ensure_procs(conn)
            print("[start_server] 存储过程/函数/触发器创建完成！")
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
