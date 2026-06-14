from __future__ import annotations


import datetime
import hashlib
import json
import os
import time

from flask import Blueprint, jsonify, request, session, send_from_directory

from config import Config
from db import call_proc, execute, fetch_all, fetch_one

api = Blueprint("api", __name__)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _require_login() -> int | None:
    return session.get("user_id")


def _require_role(role: str) -> bool:
    return session.get("role") == role


@api.post("/api/register")
def register():
    if request.content_type and "multipart/form-data" in request.content_type:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "player")
        avatar_file = request.files.get("avatar")
    else:
        payload = request.get_json(force=True)
        username = payload.get("username", "").strip()
        password = payload.get("password", "")
        role = payload.get("role", "player")
        avatar_file = None

    if not username or not password or role not in {"player", "publisher"}:
        return jsonify({"error": "invalid input"}), 400

    password_hash = _hash_password(password)
    avatar_path = "uploads/default_avatar.svg"
    if avatar_file and avatar_file.filename:
        timestamp = int(time.time())
        os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
        filename = f"{timestamp}_avatar_{avatar_file.filename}"
        file_path = os.path.join(Config.UPLOAD_DIR, filename)
        avatar_file.save(file_path)
        avatar_path = os.path.join("uploads", filename).replace("\\", "/")
    try:
        user_id = execute(
            "INSERT INTO Users(username, password_hash, role, avatar_path) VALUES (%s, %s, %s, %s)",
            (username, password_hash, role, avatar_path),
        )
    except Exception as exc:  # pragma: no cover - db constraint error
        message = str(exc)
        if "Duplicate" in message or "duplicate" in message:
            return jsonify({"error": "用户名已存在"}), 400
        return jsonify({"error": message}), 400

    # Return the user data directly without re-querying
    return jsonify({
        "user_id": user_id,
        "username": username,
        "role": role,
        "avatar_path": avatar_path,
    }), 201




@api.post("/api/login")
def login():
    payload = request.get_json(force=True)
    username = payload.get("username", "").strip()
    password = payload.get("password", "")

    user = fetch_one(
        "SELECT user_id, username, role, password_hash FROM Users WHERE username=%s",
        (username,),
    )
    if not user:
        return jsonify({"error": "user not found"}), 404

    if user["password_hash"] != _hash_password(password):
        return jsonify({"error": "invalid credentials"}), 401

    session["user_id"] = user["user_id"]
    session["role"] = user["role"]
    return jsonify({"user_id": user["user_id"], "role": user["role"]})


@api.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"status": "ok"})


@api.get("/api/me")
def me():
    user_id = session.get("user_id")
    role = session.get("role")
    if not user_id:
        return jsonify({"logged_in": False})
    user = fetch_one("SELECT username, avatar_path FROM Users WHERE user_id=%s", (user_id,))
    return jsonify(
        {
            "logged_in": True,
            "user_id": user_id,
            "role": role,
            "username": user["username"] if user else None,
            "avatar_url": f"/static/{user['avatar_path']}" if user else None,
        }
    )


@api.get("/api/users/<int:user_id>/profile")
def user_profile(user_id: int):
    viewer_id = session.get("user_id")
    user = fetch_one(
        "SELECT user_id, username, role, avatar_path, balance FROM Users WHERE user_id=%s",
        (user_id,),
    )
    if not user:
        return jsonify({"error": "user not found"}), 404


    games = fetch_all(
        """
        SELECT g.game_id, g.title, g.cover_path, o.purchased_at
        FROM Orders o
        JOIN Games g ON g.game_id = o.game_id
        WHERE o.user_id = %s
        ORDER BY o.purchased_at DESC
        """,
        (user_id,),
    )
    for game in games:
        game["cover_url"] = f"/static/{game['cover_path']}"

    is_self = viewer_id == user_id if viewer_id else False
    is_friend = False
    pending = None
    pending_id = None

    if viewer_id and not is_self:
        friend = fetch_one(
            "SELECT 1 FROM Friends WHERE user_id=%s AND friend_id=%s",
            (viewer_id, user_id),
        )
        is_friend = bool(friend)
        request = fetch_one(
            """
            SELECT request_id, from_user_id, to_user_id, status
            FROM FriendRequests
            WHERE (from_user_id=%s AND to_user_id=%s)
               OR (from_user_id=%s AND to_user_id=%s)
            ORDER BY request_id DESC
            LIMIT 1
            """,
            (viewer_id, user_id, user_id, viewer_id),
        )
        if request and request["status"] == "pending":
            pending_id = request["request_id"]
            if request["from_user_id"] == viewer_id:
                pending = "sent"
            else:
                pending = "received"

    return jsonify(
        {
            "user_id": user["user_id"],
            "username": user["username"],
            "role": user["role"],
            "avatar_url": f"/static/{user['avatar_path']}",
            "balance": float(user["balance"]),
            "owned_games": games,
            "is_self": is_self,
            "is_friend": is_friend,
            "pending_request": pending,
            "pending_request_id": pending_id,
        }
    )



@api.get("/api/users/search")
def search_users():
    user_id = session.get("user_id")
    keyword = request.args.get("username", "").strip()
    if not keyword:
        return jsonify([])

    users = fetch_all(
        """
        SELECT user_id, username, avatar_path
        FROM Users
        WHERE username LIKE %s
        ORDER BY username ASC
        LIMIT 20
        """,
        (f"%{keyword}%",),
    )
    result = []
    for user in users:
        if user_id and user["user_id"] == user_id:
            continue
        result.append(
            {
                "user_id": user["user_id"],
                "username": user["username"],
                "avatar_url": f"/static/{user['avatar_path']}",
            }
        )
    return jsonify(result)


@api.post("/api/friends/requests")
def create_friend_request():
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(force=True)
    to_user_id = payload.get("to_user_id")
    message = (payload.get("message") or "").strip()
    if not to_user_id:
        return jsonify({"error": "invalid input"}), 400
    if int(to_user_id) == int(user_id):
        return jsonify({"error": "cannot add yourself"}), 400
    if len(message) > 30:
        return jsonify({"error": "message too long"}), 400

    exists = fetch_one(
        "SELECT 1 FROM Friends WHERE user_id=%s AND friend_id=%s",
        (user_id, to_user_id),
    )
    if exists:
        return jsonify({"error": "already friends"}), 400

    request_row = fetch_one(
        """
        SELECT request_id, from_user_id, to_user_id, status
        FROM FriendRequests
        WHERE (from_user_id=%s AND to_user_id=%s)
           OR (from_user_id=%s AND to_user_id=%s)
        ORDER BY request_id DESC
        LIMIT 1
        """,
        (user_id, to_user_id, to_user_id, user_id),
    )
    if request_row:
        # 如果之前有一条 rejected 的申请，update 它重新变为 pending（因为唯一约束不允许重复 insert）
        if request_row["status"] == "rejected":
            execute(
                "UPDATE FriendRequests SET status='pending', message=%s, created_at=CURRENT_TIMESTAMP WHERE request_id=%s",
                (message, request_row["request_id"]),
            )
            return jsonify({"status": "sent"}), 201

        if request_row["status"] == "pending":
            # If the other user already sent a request to us, auto-accept it
            if int(request_row["from_user_id"]) == int(to_user_id) and int(request_row["to_user_id"]) == int(user_id):
                execute(
                    "UPDATE FriendRequests SET status='accepted' WHERE request_id=%s",
                    (request_row["request_id"],),
                )
                execute(
                    "INSERT IGNORE INTO Friends(user_id, friend_id) VALUES (%s, %s)",
                    (request_row["from_user_id"], request_row["to_user_id"]),
                )
                execute(
                    "INSERT IGNORE INTO Friends(user_id, friend_id) VALUES (%s, %s)",
                    (request_row["to_user_id"], request_row["from_user_id"]),
                )
                return jsonify({"status": "accepted"}), 200
            return jsonify({"error": "request pending"}), 400

    execute(
        """
        INSERT INTO FriendRequests(from_user_id, to_user_id, message)
        VALUES (%s, %s, %s)
        """,
        (user_id, to_user_id, message),
    )
    return jsonify({"status": "sent"}), 201


@api.get("/api/friends/requests")
def list_friend_requests():
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    requests = fetch_all(
        """
        SELECT fr.request_id, fr.message, fr.created_at,
               u.user_id AS from_user_id, u.username AS from_username, u.avatar_path
        FROM FriendRequests fr
        JOIN Users u ON u.user_id = fr.from_user_id
        WHERE fr.to_user_id = %s AND fr.status = 'pending'
        ORDER BY fr.created_at DESC
        """,
        (user_id,),
    )

    for req in requests:
        req["avatar_url"] = f"/static/{req['avatar_path']}"
    return jsonify(requests)



@api.post("/api/friends/requests/<int:request_id>/accept")
def accept_friend_request(request_id: int):
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    request_row = fetch_one(
        """
        SELECT request_id, from_user_id, to_user_id, status
        FROM FriendRequests
        WHERE request_id = %s
        """,
        (request_id,),
    )
    if not request_row or request_row["to_user_id"] != user_id:
        return jsonify({"error": "request not found"}), 404
    if request_row["status"] != "pending":
        return jsonify({"error": "request handled"}), 400

    execute(
        "UPDATE FriendRequests SET status='accepted' WHERE request_id=%s",
        (request_id,),
    )
    execute(
        "INSERT IGNORE INTO Friends(user_id, friend_id) VALUES (%s, %s)",
        (request_row["from_user_id"], request_row["to_user_id"]),
    )
    execute(
        "INSERT IGNORE INTO Friends(user_id, friend_id) VALUES (%s, %s)",
        (request_row["to_user_id"], request_row["from_user_id"]),
    )
    return jsonify({"status": "accepted"})


@api.post("/api/friends/requests/<int:request_id>/reject")
def reject_friend_request(request_id: int):
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    request_row = fetch_one(
        "SELECT request_id, to_user_id, status FROM FriendRequests WHERE request_id=%s",
        (request_id,),
    )
    if not request_row or request_row["to_user_id"] != user_id:
        return jsonify({"error": "request not found"}), 404
    if request_row["status"] != "pending":
        return jsonify({"error": "request handled"}), 400

    execute(
        "UPDATE FriendRequests SET status='rejected' WHERE request_id=%s",
        (request_id,),
    )
    return jsonify({"status": "rejected"})


@api.get("/api/friends")
def list_friends():
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    friends = fetch_all(
        """
        SELECT u.user_id AS friend_id, u.username, u.avatar_path
        FROM Friends f
        JOIN Users u ON u.user_id = f.friend_id
        WHERE f.user_id = %s
        ORDER BY u.username ASC
        """,
        (user_id,),
    )
    for friend in friends:
        friend["avatar_url"] = f"/static/{friend['avatar_path']}"
    return jsonify(friends)


@api.get("/api/games")
def list_games():
    keyword = request.args.get("q", "").strip()
    if keyword:
        games = fetch_all(
            """
            SELECT game_id, title, price, avg_rating, review_count, cover_path
            FROM Games
            WHERE title LIKE %s
            ORDER BY avg_rating DESC, review_count DESC
            """,
            (f"%{keyword}%",),
        )
    else:
        games = fetch_all(
            """
            SELECT game_id, title, price, avg_rating, review_count, cover_path
            FROM Games
            """
        )
    for game in games:
        game["cover_url"] = f"/static/{game['cover_path']}"
    return jsonify(games)



@api.get("/api/ads")
def list_ads():
    ads = fetch_all(
        """
        SELECT
            a.ad_id,
            a.title AS ad_title,
            a.content AS ad_content,
            a.created_at,
            g.game_id,
            g.title AS game_title,
            g.price,
            g.package_path,
            JSON_ARRAYAGG(ai.image_path) AS image_paths
        FROM Ads a
        JOIN Games g ON g.game_id = a.game_id
        LEFT JOIN AdImages ai ON ai.ad_id = a.ad_id
        GROUP BY a.ad_id, a.title, a.content, a.created_at, g.game_id, g.title, g.price, g.package_path
        ORDER BY a.created_at DESC
        """
    )
    for ad in ads:
        paths = ad.get("image_paths") or []
        if isinstance(paths, str):
            try:
                paths = json.loads(paths)
            except json.JSONDecodeError:
                paths = []
        ad["image_urls"] = [f"/static/{path}" for path in paths if path]
        ad["package_url"] = f"/static/{ad['package_path']}"
    return jsonify(ads)


@api.get("/api/top-rated")
def top_rated():
    games = call_proc("GetTopRatedGames")
    for game in games:
        if "cover_path" in game:
            game["cover_url"] = f"/static/{game['cover_path']}"
    return jsonify(games)


@api.get("/api/top-selling")
def top_selling():
    games = call_proc("GetTopSellingGames")
    for game in games:
        if "cover_path" in game:
            game["cover_url"] = f"/static/{game['cover_path']}"
    return jsonify(games)


@api.get("/api/games-by-price")

def games_by_price():
    desc = request.args.get("desc", "1")
    p_desc = 1 if desc == "1" else 0
    games = call_proc("GetGamesByPrice", (p_desc,))
    for game in games:
        if "cover_path" in game:
            game["cover_url"] = f"/static/{game['cover_path']}"
    return jsonify(games)


@api.get("/api/game/<int:game_id>")
def game_detail(game_id: int):
    game = fetch_one(
        """
        SELECT g.*
        FROM Games g
        WHERE g.game_id = %s
        """,
        (game_id,),
    )
    if not game:
        return jsonify({"error": "game not found"}), 404
    game["cover_url"] = f"/static/{game['cover_path']}"
    game["video_url"] = f"/static/{game['video_path']}"
    # Compute steam status label from avg_rating
    avg = game.get("avg_rating")
    if avg is None:
        game["steam_status"] = "暂无评价"
    elif avg >= 4.5:
        game["steam_status"] = "好评如潮"
    elif avg >= 3.0:
        game["steam_status"] = "褒贬不一"
    else:
        game["steam_status"] = "差评如潮"
    return jsonify(game)


@api.get("/api/game/<int:game_id>/purchase-status")
def purchase_status(game_id: int):
    user_id = _require_login()
    if not user_id:
        return jsonify({"purchased": False})
    purchased = fetch_one(
        "SELECT order_id FROM Orders WHERE user_id=%s AND game_id=%s",
        (user_id, game_id),
    )
    return jsonify({"purchased": bool(purchased)})


@api.get("/api/game/<int:game_id>/download")
def download_package(game_id: int):
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    purchased = fetch_one(
        "SELECT order_id FROM Orders WHERE user_id=%s AND game_id=%s",
        (user_id, game_id),
    )
    if not purchased:
        return jsonify({"error": "not purchased"}), 403

    game = fetch_one("SELECT package_path FROM Games WHERE game_id=%s", (game_id,))
    if not game:
        return jsonify({"error": "game not found"}), 404

    file_path = os.path.join(Config.BASE_DIR, "static", game["package_path"])
    directory, filename = os.path.split(file_path)
    return send_from_directory(directory, filename, as_attachment=True)


@api.post("/api/top-up")
def top_up():
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(force=True)
    amount = payload.get("amount")

    if not amount or not isinstance(amount, int) or amount <= 0:
        return jsonify({"error": "充值金额必须为正整数"}), 400
    if amount > 1000000:
        return jsonify({"error": "单次充值金额不能超过 1,000,000"}), 400


    execute(
        "UPDATE Users SET balance = balance + %s WHERE user_id = %s",
        (amount, user_id),
    )

    user = fetch_one("SELECT balance FROM Users WHERE user_id=%s", (user_id,))
    return jsonify({"status": "ok", "balance": float(user["balance"])})


@api.post("/api/purchase")

def purchase():
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    if not _require_role("player"):
        return jsonify({"error": "发行商账号不能购买游戏"}), 403

    payload = request.get_json(force=True)
    game_id = payload.get("game_id")
    if not game_id:
        return jsonify({"error": "game_id required"}), 400

    try:
        call_proc("PurchaseGameTransaction", (user_id, int(game_id)))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "purchased"})


@api.post("/api/review")
def review():
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    if not _require_role("player"):
        return jsonify({"error": "发行商账号不能发表评价"}), 403

    payload = request.get_json(force=True)
    game_id = payload.get("game_id")
    rating = payload.get("rating")
    content = payload.get("content", "").strip()

    if not game_id or not rating or not content:
        return jsonify({"error": "invalid input"}), 400

    purchased = fetch_one(
        "SELECT order_id FROM Orders WHERE user_id=%s AND game_id=%s",
        (user_id, game_id),
    )
    if not purchased:
        return jsonify({"error": "not purchased"}), 403

    try:
        execute(
            "INSERT INTO Reviews(user_id, game_id, rating, content) VALUES (%s, %s, %s, %s)",
            (user_id, game_id, rating, content),
        )
    except Exception as exc:
        err_str = str(exc)
        if "Duplicate entry" in err_str and "uq_reviews_user_game" in err_str:
            return jsonify({"error": "你已经评价过这个游戏了，不能重复评价"}), 400
        return jsonify({"error": err_str}), 400


    return jsonify({"status": "reviewed"}), 201


@api.get("/api/game/<int:game_id>/reviews")
def game_reviews(game_id: int):
    reviews = fetch_all(
        """
        SELECT r.review_id, r.rating, r.content, r.created_at,
               u.user_id, u.username
        FROM Reviews r
        JOIN Users u ON u.user_id = r.user_id
        WHERE r.game_id = %s
        ORDER BY r.created_at DESC
        """,
        (game_id,),
    )
    if not reviews:
        return jsonify([])

    review_ids = [review["review_id"] for review in reviews]
    placeholders = ",".join(["%s"] * len(review_ids))
    replies = fetch_all(
        f"""
        SELECT rr.reply_id, rr.review_id, rr.content, rr.created_at,
               u.user_id AS user_id, u.username AS username, u.avatar_path AS avatar_path,
               ru.user_id AS reply_to_user_id, ru.username AS reply_to_username
        FROM ReviewReplies rr
        JOIN Users u ON u.user_id = rr.user_id
        JOIN Users ru ON ru.user_id = rr.reply_to_user_id
        WHERE rr.review_id IN ({placeholders})
        ORDER BY rr.created_at ASC
        """,
        tuple(review_ids),
    )

    reply_map: dict[int, list[dict]] = {review_id: [] for review_id in review_ids}
    for reply in replies:
        reply["avatar_url"] = f"/static/{reply['avatar_path']}" if reply.get("avatar_path") else None
        reply_map[reply["review_id"]].append(reply)

    for review in reviews:
        review["replies"] = reply_map.get(review["review_id"], [])

    return jsonify(reviews)


@api.post("/api/review-replies")
def create_review_reply():
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(force=True)
    review_id = payload.get("review_id")
    reply_to_user_id = payload.get("reply_to_user_id")
    content = payload.get("content", "").strip()

    if not review_id or not content:
        return jsonify({"error": "invalid input"}), 400

    review = fetch_one(
        "SELECT review_id, user_id FROM Reviews WHERE review_id=%s",
        (review_id,),
    )
    if not review:
        return jsonify({"error": "review not found"}), 404

    if not reply_to_user_id:
        reply_to_user_id = review["user_id"]

    target = fetch_one("SELECT user_id FROM Users WHERE user_id=%s", (reply_to_user_id,))
    if not target:
        return jsonify({"error": "reply user not found"}), 404

    execute(
        """
        INSERT INTO ReviewReplies(review_id, user_id, reply_to_user_id, content)
        VALUES (%s, %s, %s, %s)
        """,
        (review_id, user_id, reply_to_user_id, content),
    )

    return jsonify({"status": "replied"}), 201


@api.post("/api/publisher/games")
def publisher_create_game():
    user_id = _require_login()
    if not user_id or not _require_role("publisher"):
        return jsonify({"error": "unauthorized"}), 401

    title = request.form.get("title", "").strip()
    price = request.form.get("price")
    cover_file = request.files.get("cover")
    video_file = request.files.get("video")
    package_file = request.files.get("package")

    if not title or price is None or not cover_file or not video_file or not package_file:
        return jsonify({"error": "invalid input"}), 400

    timestamp = int(time.time())
    os.makedirs(Config.UPLOAD_DIR, exist_ok=True)

    cover_name = f"{timestamp}_cover_{cover_file.filename}"
    video_name = f"{timestamp}_video_{video_file.filename}"
    package_name = f"{timestamp}_package_{package_file.filename}"

    cover_path = os.path.join(Config.UPLOAD_DIR, cover_name)
    video_path = os.path.join(Config.UPLOAD_DIR, video_name)
    package_path = os.path.join(Config.UPLOAD_DIR, package_name)

    cover_file.save(cover_path)
    video_file.save(video_path)
    package_file.save(package_path)

    rel_cover = os.path.join("uploads", cover_name).replace("\\", "/")
    rel_video = os.path.join("uploads", video_name).replace("\\", "/")
    rel_package = os.path.join("uploads", package_name).replace("\\", "/")

    execute(
        """
        INSERT INTO Games(publisher_id, title, price, cover_path, video_path, package_path)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (user_id, title, price, rel_cover, rel_video, rel_package),
    )

    return jsonify({"status": "created"}), 201


@api.get("/api/publisher/my-games")
def publisher_games():
    user_id = _require_login()
    if not user_id or not _require_role("publisher"):
        return jsonify({"error": "unauthorized"}), 401

    games = fetch_all(
        """
        SELECT game_id, title, price
        FROM Games
        WHERE publisher_id = %s
        ORDER BY created_at DESC
        """,
        (user_id,),
    )
    return jsonify(games)


@api.post("/api/publisher/ads")
def publisher_create_ad():
    user_id = _require_login()
    if not user_id or not _require_role("publisher"):
        return jsonify({"error": "unauthorized"}), 401

    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    game_id = request.form.get("game_id")
    images = request.files.getlist("images")

    if not title or not content or not game_id:
        return jsonify({"error": "invalid input"}), 400
    if not images or len(images) > 4:
        return jsonify({"error": "images must be 1-4"}), 400

    game = fetch_one(
        "SELECT game_id FROM Games WHERE game_id=%s AND publisher_id=%s",
        (game_id, user_id),
    )
    if not game:
        return jsonify({"error": "game not found"}), 404

    timestamp = int(time.time())
    os.makedirs(Config.UPLOAD_DIR, exist_ok=True)

    execute(
        "INSERT INTO Ads(publisher_id, game_id, title, content) VALUES (%s, %s, %s, %s)",
        (user_id, game_id, title, content),
    )
    ad = fetch_one(
        "SELECT ad_id FROM Ads WHERE publisher_id=%s AND game_id=%s ORDER BY ad_id DESC LIMIT 1",
        (user_id, game_id),
    )
    ad_id = ad["ad_id"]

    image_paths = []
    for index, image in enumerate(images, start=1):
        filename = f"{timestamp}_ad_{ad_id}_{index}_{image.filename}"
        path = os.path.join(Config.UPLOAD_DIR, filename)
        image.save(path)
        rel_path = os.path.join("uploads", filename).replace("\\", "/")
        image_paths.append(rel_path)
        execute(
            "INSERT INTO AdImages(ad_id, image_path) VALUES (%s, %s)",
            (ad_id, rel_path),
        )

    return jsonify({"status": "created", "ad_id": ad_id, "image_paths": image_paths}), 201


@api.get("/api/mail")
def list_mail():
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    mails = fetch_all(
        """
        SELECT m.mail_id, m.content, m.image_path, m.created_at,
               u.user_id AS from_user_id, u.username AS from_username, u.avatar_path
        FROM Mail m
        JOIN Users u ON u.user_id = m.sender_id
        WHERE m.receiver_id = %s
        ORDER BY m.created_at DESC
        """,
        (user_id,),
    )
    for mail in mails:
        mail["from_avatar_url"] = f"/static/{mail['avatar_path']}"
        mail["image_url"] = f"/static/{mail['image_path']}" if mail.get("image_path") else None
    return jsonify(mails)


@api.get("/api/mail/<int:mail_id>")
def get_mail_detail(mail_id: int):
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    mail = fetch_one(
        """
        SELECT m.mail_id, m.content, m.image_path, m.game_id, m.created_at,
               u.user_id AS from_user_id, u.username AS from_username, u.avatar_path
        FROM Mail m
        JOIN Users u ON u.user_id = m.sender_id
        WHERE m.mail_id = %s AND m.receiver_id = %s
        """,
        (mail_id, user_id),
    )
    if not mail:
        return jsonify({"error": "mail not found"}), 404

    mail["from_avatar_url"] = f"/static/{mail['avatar_path']}"
    mail["image_url"] = f"/static/{mail['image_path']}" if mail.get("image_path") else None

    # Get game info if available
    if mail.get("game_id"):
        game = fetch_one(
            "SELECT game_id, title FROM Games WHERE game_id=%s",
            (mail["game_id"],),
        )
        mail["game"] = game

    return jsonify(mail)


@api.post("/api/publisher/mail")

def publisher_send_mail():
    try:
        user_id = _require_login()
        if not user_id or not _require_role("publisher"):
            return jsonify({"error": "unauthorized"}), 401

        content = request.form.get("content", "").strip()
        game_id = request.form.get("game_id")
        image_file = request.files.get("image")

        if not game_id:
            return jsonify({"error": "invalid input"}), 400
        
        # Check if image_file is actually provided (not just an empty file input)
        has_image = image_file and image_file.filename
        
        if content and has_image:
            return jsonify({"error": "text or image only"}), 400
        if not content and not has_image:
            return jsonify({"error": "text or image required"}), 400

        game = fetch_one(
            "SELECT game_id FROM Games WHERE game_id=%s AND publisher_id=%s",
            (game_id, user_id),
        )
        if not game:
            return jsonify({"error": "game not found"}), 404

        image_path = None
        if image_file:
            timestamp = int(time.time())
            os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
            filename = f"{timestamp}_mail_{image_file.filename}"
            file_path = os.path.join(Config.UPLOAD_DIR, filename)
            image_file.save(file_path)
            image_path = os.path.join("uploads", filename).replace("\\", "/")

        owners = fetch_all(
            "SELECT DISTINCT user_id FROM Orders WHERE game_id=%s",
            (game_id,),
        )
        for owner in owners:
            execute(
                """
                INSERT INTO Mail(sender_id, receiver_id, game_id, content, image_path)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, owner["user_id"], game_id, content or None, image_path),
            )

        return jsonify({"status": "sent", "count": len(owners)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== Friend Chat API =====

@api.post("/api/friend-chat/send")
def send_friend_message():
    user_id = _require_login()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    receiver_id = request.form.get("receiver_id")
    content = request.form.get("content", "").strip()
    image_file = request.files.get("image")

    if not receiver_id:
        return jsonify({"error": "receiver_id required"}), 400

    receiver_id = int(receiver_id)

    # Verify they are friends
    friend = fetch_one(
        "SELECT 1 FROM Friends WHERE user_id=%s AND friend_id=%s",
        (user_id, receiver_id),
    )
    if not friend:
        return jsonify({"error": "not friends"}), 403

    # Check content/image mutual exclusion
    has_content = bool(content)
    has_image = bool(image_file and image_file.filename)
    if has_content and has_image:
        return jsonify({"error": "text or image only"}), 400
    if not has_content and not has_image:
        return jsonify({"error": "text or image required"}), 400

    image_path = None
    if has_image:
        timestamp = int(time.time())
        os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
        filename = f"{timestamp}_chat_{image_file.filename}"
        file_path = os.path.join(Config.UPLOAD_DIR, filename)
        image_file.save(file_path)
        image_path = os.path.join("uploads", filename).replace("\\", "/")

    execute(
        """
        INSERT INTO FriendMessages(sender_id, receiver_id, content, image_path)
        VALUES (%s, %s, %s, %s)
        """,
        (user_id, receiver_id, content or None, image_path),
    )

    return jsonify({"status": "sent"}), 201


@api.get("/api/friend-chat/<int:friend_id>")
def get_friend_chat(friend_id: int):
    try:
        user_id = _require_login()
        if not user_id:
            return jsonify({"error": "unauthorized"}), 401

        # Verify they are friends
        friend = fetch_one(
            "SELECT 1 FROM Friends WHERE user_id=%s AND friend_id=%s",
            (user_id, friend_id),
        )
        if not friend:
            return jsonify({"error": "not friends"}), 403

        # Get friend info
        friend_info = fetch_one(
            "SELECT user_id, username, avatar_path FROM Users WHERE user_id=%s",
            (friend_id,),
        )
        if not friend_info:
            return jsonify({"error": "user not found"}), 404

        # Get messages between the two users
        messages = fetch_all(
            """
            SELECT msg_id, sender_id, receiver_id, content, image_path, created_at
            FROM FriendMessages
            WHERE (sender_id = %s AND receiver_id = %s)
               OR (sender_id = %s AND receiver_id = %s)
            ORDER BY created_at ASC
            """,
            (user_id, friend_id, friend_id, user_id),
        )

        for msg in messages:
            msg["image_url"] = f"/static/{msg['image_path']}" if msg.get("image_path") else None
            msg["is_me"] = (msg["sender_id"] == user_id)
            # Convert datetime to ISO string for consistent frontend parsing
            if isinstance(msg.get("created_at"), datetime.datetime):
                msg["created_at"] = msg["created_at"].strftime("%Y-%m-%d %H:%M:%S")

        return jsonify({
            "friend": {
                "user_id": friend_info["user_id"],
                "username": friend_info["username"],
                "avatar_url": f"/static/{friend_info['avatar_path']}",
            },
            "messages": messages,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


