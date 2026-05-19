-- Phase 1: Schema + Advanced DB Objects for Game Hub Game Platform
-- MySQL 8.0

CREATE DATABASE IF NOT EXISTS steam_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE steam_platform;


-- Drop objects in dependency order
DROP TRIGGER IF EXISTS After_Review_Insert;
DROP PROCEDURE IF EXISTS GetTopRatedGames;
DROP PROCEDURE IF EXISTS GetGamesByPrice;
DROP PROCEDURE IF EXISTS PurchaseGameTransaction;
DROP FUNCTION IF EXISTS GetSteamStatus;

DROP TABLE IF EXISTS AdImages;
DROP TABLE IF EXISTS Ads;
DROP TABLE IF EXISTS ReviewReplies;
DROP TABLE IF EXISTS Reviews;
DROP TABLE IF EXISTS FriendRequests;
DROP TABLE IF EXISTS Friends;
DROP TABLE IF EXISTS Mail;
DROP TABLE IF EXISTS Orders;
DROP TABLE IF EXISTS Games;
DROP TABLE IF EXISTS Users;

-- Users table
CREATE TABLE Users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('player', 'publisher') NOT NULL,
    avatar_path VARCHAR(255) NOT NULL,
    balance DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Games table
CREATE TABLE Games (
    game_id INT AUTO_INCREMENT PRIMARY KEY,
    publisher_id INT NOT NULL,
    title VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    avg_rating DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    review_count INT NOT NULL DEFAULT 0,
    cover_path VARCHAR(255) NOT NULL,
    video_path VARCHAR(255) NOT NULL,
    package_path VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_games_publisher
        FOREIGN KEY (publisher_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE INDEX idx_games_price ON Games(price);
CREATE INDEX idx_games_rating ON Games(avg_rating, review_count);

-- Ads table
CREATE TABLE Ads (
    ad_id INT AUTO_INCREMENT PRIMARY KEY,
    publisher_id INT NOT NULL,
    game_id INT NOT NULL,
    title VARCHAR(120) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ads_publisher
        FOREIGN KEY (publisher_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_ads_game
        FOREIGN KEY (game_id) REFERENCES Games(game_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE INDEX idx_ads_game ON Ads(game_id);

-- Ad images table (up to 4 images per ad)
CREATE TABLE AdImages (
    ad_image_id INT AUTO_INCREMENT PRIMARY KEY,
    ad_id INT NOT NULL,
    image_path VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ad_images_ad
        FOREIGN KEY (ad_id) REFERENCES Ads(ad_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- Orders table
CREATE TABLE Orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    game_id INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    purchased_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_orders_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_orders_game
        FOREIGN KEY (game_id) REFERENCES Games(game_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_orders_user_game UNIQUE (user_id, game_id)
) ENGINE=InnoDB;

-- Reviews table
CREATE TABLE Reviews (
    review_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    game_id INT NOT NULL,
    rating INT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_reviews_rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT fk_reviews_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_reviews_game
        FOREIGN KEY (game_id) REFERENCES Games(game_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_reviews_user_game UNIQUE (user_id, game_id)
) ENGINE=InnoDB;

-- Review replies (flat under a review)
CREATE TABLE ReviewReplies (
    reply_id INT AUTO_INCREMENT PRIMARY KEY,
    review_id INT NOT NULL,
    user_id INT NOT NULL,
    reply_to_user_id INT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reply_review
        FOREIGN KEY (review_id) REFERENCES Reviews(review_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_reply_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_reply_to_user
        FOREIGN KEY (reply_to_user_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Friend requests
CREATE TABLE FriendRequests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    from_user_id INT NOT NULL,
    to_user_id INT NOT NULL,
    message VARCHAR(30) NOT NULL DEFAULT '',
    status ENUM('pending', 'accepted', 'rejected') NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_friend_request_from
        FOREIGN KEY (from_user_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_friend_request_to
        FOREIGN KEY (to_user_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_friend_request UNIQUE (from_user_id, to_user_id)
) ENGINE=InnoDB;

-- Friends (bidirectional rows)
CREATE TABLE Friends (
    user_id INT NOT NULL,
    friend_id INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, friend_id),
    CONSTRAINT fk_friends_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_friends_friend
        FOREIGN KEY (friend_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- Mail inbox
CREATE TABLE Mail (
    mail_id INT AUTO_INCREMENT PRIMARY KEY,
    from_user_id INT NOT NULL,
    to_user_id INT NOT NULL,
    subject VARCHAR(80) NOT NULL,
    content TEXT NULL,
    image_path VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mail_from
        FOREIGN KEY (from_user_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_mail_to
        FOREIGN KEY (to_user_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

DELIMITER $$

-- Stored Procedure: Top Rated Games
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
END$$

-- Stored Procedure: Games By Price (p_desc = 1 for DESC, 0 for ASC)
CREATE PROCEDURE GetGamesByPrice(IN p_desc TINYINT)
BEGIN
    IF p_desc = 1 THEN
        SELECT
            g.game_id,
            g.title,
            g.price,
            g.avg_rating,
            g.review_count,
            g.cover_path
        FROM Games g
        ORDER BY g.price DESC
        LIMIT 10;
    ELSE
        SELECT
            g.game_id,
            g.title,
            g.price,
            g.avg_rating,
            g.review_count,
            g.cover_path
        FROM Games g
        ORDER BY g.price ASC
        LIMIT 10;
    END IF;
END$$

-- Function: Game Hub status label
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
END$$

-- Trigger: After Review Insert
CREATE TRIGGER After_Review_Insert
AFTER INSERT ON Reviews
FOR EACH ROW
BEGIN
    UPDATE Games g
    SET
        g.avg_rating = (
            SELECT ROUND(AVG(r.rating), 2) FROM Reviews r WHERE r.game_id = NEW.game_id
        ),
        g.review_count = (
            SELECT COUNT(*) FROM Reviews r WHERE r.game_id = NEW.game_id
        )
    WHERE g.game_id = NEW.game_id;
END$$

-- Stored Procedure: Top Selling Games (by order count)
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
END$$

-- Stored Procedure: Purchase Transaction

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

    SELECT price, publisher_id
    INTO v_price, v_publisher_id
    FROM Games
    WHERE game_id = p_game_id
    FOR UPDATE;

    IF v_price IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Game not found';
    END IF;

    SELECT balance INTO v_balance
    FROM Users
    WHERE user_id = p_user_id
    FOR UPDATE;

    IF v_balance IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'User not found';
    END IF;

    SELECT COUNT(*) INTO v_exists
    FROM Orders
    WHERE user_id = p_user_id AND game_id = p_game_id;

    IF v_exists > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Already purchased';
    END IF;

    IF v_balance < v_price THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Insufficient balance';
    END IF;

    UPDATE Users
    SET balance = balance - v_price
    WHERE user_id = p_user_id;

    UPDATE Users
    SET balance = balance + v_price
    WHERE user_id = v_publisher_id;

    INSERT INTO Orders(user_id, game_id, price)
    VALUES (p_user_id, p_game_id, v_price);

    COMMIT;
END$$

DELIMITER ;
