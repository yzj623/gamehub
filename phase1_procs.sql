-- Stored Procedures, Functions, and Triggers for Game Hub
-- This file is re-imported on every server start to ensure they exist

DROP PROCEDURE IF EXISTS GetTopRatedGames;
DROP PROCEDURE IF EXISTS GetGamesByPrice;
DROP PROCEDURE IF EXISTS GetTopSellingGames;
DROP PROCEDURE IF EXISTS PurchaseGameTransaction;
DROP FUNCTION IF EXISTS GetSteamStatus;
DROP TRIGGER IF EXISTS After_Review_Insert;

DELIMITER $$

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
