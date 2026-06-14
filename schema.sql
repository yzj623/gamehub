-- ============================================================
-- Game Hub（游戏中心）完整数据库 Schema
-- 包含：表结构 + 存储过程 + 函数 + 触发器
-- ============================================================

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS steam_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE steam_platform;

-- ============================================================
-- 删除已有对象（按依赖顺序）
-- 先删触发器，再删存储过程和函数，最后删表

-- ============================================================
DROP TRIGGER IF EXISTS After_Review_Insert;
DROP PROCEDURE IF EXISTS GetTopRatedGames;
DROP PROCEDURE IF EXISTS GetGamesByPrice;
DROP PROCEDURE IF EXISTS GetTopSellingGames;
DROP PROCEDURE IF EXISTS PurchaseGameTransaction;
DROP FUNCTION IF EXISTS GetSteamStatus;

DROP TABLE IF EXISTS FriendMessages;        -- 好友私聊消息（依赖 Users）
DROP TABLE IF EXISTS AdImages;              -- 广告图片（依赖 Ads）
DROP TABLE IF EXISTS Ads;                   -- 广告（依赖 Users, Games）
DROP TABLE IF EXISTS ReviewReplies;         -- 评价回复（依赖 Reviews, Users）
DROP TABLE IF EXISTS Reviews;               -- 评价（依赖 Users, Games）
DROP TABLE IF EXISTS FriendRequests;        -- 好友申请（依赖 Users）
DROP TABLE IF EXISTS Friends;               -- 好友关系（依赖 Users）
DROP TABLE IF EXISTS Mail;                  -- 站内信（依赖 Users, Games）
DROP TABLE IF EXISTS Orders;                -- 订单（依赖 Users, Games）
DROP TABLE IF EXISTS Games;                 -- 游戏（依赖 Users）
DROP TABLE IF EXISTS Users;                 -- 用户（最基础的表，最后删）

-- ============================================================
-- 表结构
-- ============================================================

-- ========== 用户表 ==========
-- 存储所有用户（玩家和发行商）的基本信息
CREATE TABLE Users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,                     -- 用户ID，自增主键
    username VARCHAR(50) NOT NULL UNIQUE,                       -- 用户名，唯一
    password_hash VARCHAR(255) NOT NULL,                        -- 密码的 SHA-256 哈希值
    role ENUM('player', 'publisher') NOT NULL,                  -- 角色：player=玩家, publisher=发行商
    avatar_path VARCHAR(255) NOT NULL,                          -- 头像图片文件路径
    balance DECIMAL(10,2) NOT NULL DEFAULT 0.00,               -- 账户余额（精确到分）
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP     -- 注册时间
) ENGINE=InnoDB;

-- ========== 游戏表 ==========
-- 存储所有游戏的详细信息
CREATE TABLE Games (
    game_id INT AUTO_INCREMENT PRIMARY KEY,                     -- 游戏ID，自增主键
    publisher_id INT NOT NULL,                                  -- 发行商用户ID（关联 Users）
    title VARCHAR(100) NOT NULL,                                -- 游戏标题
    price DECIMAL(10,2) NOT NULL,                               -- 游戏价格
    avg_rating DECIMAL(3,2) NOT NULL DEFAULT 0.00,             -- 平均评分（由触发器自动更新）
    review_count INT NOT NULL DEFAULT 0,                        -- 评价数量（由触发器自动更新）
    cover_path VARCHAR(255) NOT NULL,                           -- 封面图片路径
    video_path VARCHAR(255) NOT NULL,                           -- 宣传视频路径
    package_path VARCHAR(255) NOT NULL,                         -- 游戏安装包路径
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,    -- 发布时间
    CONSTRAINT fk_games_publisher
        FOREIGN KEY (publisher_id) REFERENCES Users(user_id)   -- 外键：发行商必须是已注册用户
        ON UPDATE CASCADE ON DELETE RESTRICT                    -- 用户ID更新时级联修改；有游戏的发行商不能被删除
) ENGINE=InnoDB;

-- 索引：加速按价格查询和排行榜排序
CREATE INDEX idx_games_price ON Games(price);
-- 复合索引：加速按评分和评价数排序（如排行榜）
CREATE INDEX idx_games_rating ON Games(avg_rating, review_count);

-- ========== 广告表 ==========
-- 发行商为自己的游戏创建的广告
CREATE TABLE Ads (
    ad_id INT AUTO_INCREMENT PRIMARY KEY,                       -- 广告ID，自增主键
    publisher_id INT NOT NULL,                                  -- 发行商ID（关联 Users）
    game_id INT NOT NULL,                                       -- 关联的游戏ID（关联 Games）
    title VARCHAR(120) NOT NULL,                                -- 广告标题
    content TEXT NOT NULL,                                      -- 广告正文
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,    -- 创建时间
    CONSTRAINT fk_ads_publisher
        FOREIGN KEY (publisher_id) REFERENCES Users(user_id)   -- 外键：广告发布者必须是已注册用户
        ON UPDATE CASCADE ON DELETE RESTRICT,                   -- 用户ID更新时级联修改；有广告存在的用户不能被删除
    CONSTRAINT fk_ads_game
        FOREIGN KEY (game_id) REFERENCES Games(game_id)        -- 外键：广告关联的游戏必须存在
        ON UPDATE CASCADE ON DELETE RESTRICT                    -- 游戏ID更新时级联修改；有关联广告的游戏不能被删除
) ENGINE=InnoDB;

-- 索引：加速按游戏ID查询广告
CREATE INDEX idx_ads_game ON Ads(game_id);

-- ========== 广告图片表 ==========

CREATE TABLE AdImages (
    ad_image_id INT AUTO_INCREMENT PRIMARY KEY,                 -- 图片ID，自增主键
    ad_id INT NOT NULL,                                         -- 所属广告ID（关联 Ads）
    image_path VARCHAR(255) NOT NULL,                           -- 图片文件路径
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,    -- 上传时间
    CONSTRAINT fk_ad_images_ad
        FOREIGN KEY (ad_id) REFERENCES Ads(ad_id)              -- 外键：图片所属的广告必须存在
        ON UPDATE CASCADE ON DELETE CASCADE                     -- 广告ID更新时级联修改；删除广告时自动删除其所有图片
) ENGINE=InnoDB;

-- ========== 订单表 ==========
-- 记录玩家的购买记录，一个用户对同一游戏只能买一次
CREATE TABLE Orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,                    -- 订单ID，自增主键
    user_id INT NOT NULL,                                       -- 买家ID（关联 Users）
    game_id INT NOT NULL,                                       -- 游戏ID（关联 Games）
    price DECIMAL(10,2) NOT NULL,                               -- 成交价格（记录购买时的价格，防止未来调价影响）
    purchased_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- 购买时间
    CONSTRAINT fk_orders_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)        -- 外键：买家必须是已注册用户
        ON UPDATE CASCADE ON DELETE RESTRICT,                   -- 用户ID更新时级联修改；有购买记录的用户不能被删除
    CONSTRAINT fk_orders_game
        FOREIGN KEY (game_id) REFERENCES Games(game_id)        -- 外键：订单对应的游戏必须存在
        ON UPDATE CASCADE ON DELETE RESTRICT,                   -- 游戏ID更新时级联修改；有关联订单的游戏不能被删除
    CONSTRAINT uq_orders_user_game UNIQUE (user_id, game_id)    -- 唯一约束：同一用户不能重复购买同一游戏
) ENGINE=InnoDB;

-- ========== 评价表 ==========
-- 玩家对已购买游戏的评价（评分 + 文字评论）
CREATE TABLE Reviews (
    review_id INT AUTO_INCREMENT PRIMARY KEY,                   -- 评价ID，自增主键
    user_id INT NOT NULL,                                       -- 评价者ID（关联 Users）
    game_id INT NOT NULL,                                       -- 被评价游戏ID（关联 Games）
    rating INT NOT NULL,                                        -- 评分（1~5 分）
    content TEXT NOT NULL,                                      -- 评价内容
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,    -- 评价时间
    CONSTRAINT chk_reviews_rating CHECK (rating BETWEEN 1 AND 5),  -- 检查约束：评分必须在 1~5 之间
    CONSTRAINT fk_reviews_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)        -- 外键：评价者必须是已注册用户
        ON UPDATE CASCADE ON DELETE RESTRICT,                   -- 用户ID更新时级联修改；发表过评价的用户不能被删除
    CONSTRAINT fk_reviews_game
        FOREIGN KEY (game_id) REFERENCES Games(game_id)        -- 外键：被评价的游戏必须存在
        ON UPDATE CASCADE ON DELETE RESTRICT,                   -- 游戏ID更新时级联修改；有关联评价的游戏不能被删除
    CONSTRAINT uq_reviews_user_game UNIQUE (user_id, game_id)    -- 唯一约束：同一用户对同一游戏只能评价一次
) ENGINE=InnoDB;

-- ========== 评价回复表 ==========
-- 对评价的回复，采用扁平结构（可回复给评价者或其他回复者）
CREATE TABLE ReviewReplies (
    reply_id INT AUTO_INCREMENT PRIMARY KEY,                    -- 回复ID，自增主键
    review_id INT NOT NULL,                                     -- 被回复的评价ID（关联 Reviews）
    user_id INT NOT NULL,                                       -- 回复者ID（关联 Users）
    reply_to_user_id INT NOT NULL,                              -- 被回复的用户ID（关联 Users）
    content TEXT NOT NULL,                                      -- 回复内容
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,    -- 回复时间
    CONSTRAINT fk_reply_review
        FOREIGN KEY (review_id) REFERENCES Reviews(review_id)  -- 外键：回复所属的评价必须存在
        ON UPDATE CASCADE ON DELETE CASCADE,                    -- 评价ID更新时级联修改；删除评价时自动删除其下所有回复
    CONSTRAINT fk_reply_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)        -- 外键：回复者必须是已注册用户
        ON UPDATE CASCADE ON DELETE RESTRICT,                   -- 用户ID更新时级联修改；发表过回复的用户不能被删除
    CONSTRAINT fk_reply_to_user
        FOREIGN KEY (reply_to_user_id) REFERENCES Users(user_id) -- 外键：被回复的用户必须是已注册用户
        ON UPDATE CASCADE ON DELETE RESTRICT                    -- 用户ID更新时级联修改；被回复过的用户不能被删除
) ENGINE=InnoDB;

-- ========== 好友申请表 ==========
-- 存储用户之间的好友申请状态
CREATE TABLE FriendRequests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,                  -- 申请ID，自增主键
    from_user_id INT NOT NULL,                                  -- 发起方用户ID（关联 Users）
    to_user_id INT NOT NULL,                                    -- 接收方用户ID（关联 Users）
    message VARCHAR(30) NOT NULL DEFAULT '',                    -- 申请附言（最多30字）
    status ENUM('pending', 'accepted', 'rejected') NOT NULL DEFAULT 'pending',  -- 状态：待处理/已接受/已拒绝
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,    -- 发送时间
    CONSTRAINT fk_friend_request_from
        FOREIGN KEY (from_user_id) REFERENCES Users(user_id)   -- 外键：申请发起方必须是已注册用户
        ON UPDATE CASCADE ON DELETE CASCADE,                    -- 用户ID更新时级联修改；用户被删除时自动删除其发出的申请
    CONSTRAINT fk_friend_request_to
        FOREIGN KEY (to_user_id) REFERENCES Users(user_id)     -- 外键：申请接收方必须是已注册用户
        ON UPDATE CASCADE ON DELETE CASCADE,                    -- 用户ID更新时级联修改；用户被删除时自动删除发给他的申请
    CONSTRAINT uq_friend_request UNIQUE (from_user_id, to_user_id)  -- 唯一约束：同一对用户只能有一条申请
) ENGINE=InnoDB;

-- ========== 好友关系表 ==========
-- 双向好友关系：A 和 B 是好友需要存储 (A,B) 和 (B,A) 两行
CREATE TABLE Friends (
    user_id INT NOT NULL,                                       -- 用户ID
    friend_id INT NOT NULL,                                     -- 好友ID
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,    -- 成为好友的时间
    PRIMARY KEY (user_id, friend_id),                           -- 联合主键
    CONSTRAINT fk_friends_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)        -- 外键：用户必须是已注册用户
        ON UPDATE CASCADE ON DELETE CASCADE,                    -- 用户ID更新时级联修改；用户被删除时自动删除他的所有好友关系
    CONSTRAINT fk_friends_friend
        FOREIGN KEY (friend_id) REFERENCES Users(user_id)      -- 外键：好友也必须是已注册用户
        ON UPDATE CASCADE ON DELETE CASCADE                     -- 好友ID更新时级联修改；好友被删除时自动删除相关关系
) ENGINE=InnoDB;

-- ========== 站内信表 ==========
-- 发行商发送给游戏购买者的通知邮件
CREATE TABLE Mail (
    mail_id INT AUTO_INCREMENT PRIMARY KEY,                     -- 邮件ID，自增主键
    sender_id INT NOT NULL,                                     -- 发送者ID（关联 Users，通常为发行商）
    receiver_id INT NOT NULL,                                   -- 接收者ID（关联 Users，通常为玩家）
    content TEXT NULL,                                          -- 邮件正文（文字和图片二选一）
    image_path VARCHAR(255) NULL,                               -- 邮件图片路径
    game_id INT NULL,                                           -- 关联的游戏ID（可选）
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,    -- 发送时间
    CONSTRAINT fk_mail_sender
        FOREIGN KEY (sender_id) REFERENCES Users(user_id)     -- 外键：邮件发送者必须是已注册用户
        ON UPDATE CASCADE ON DELETE CASCADE,                    -- 用户ID更新时级联修改；发送者被删除时自动删除其发出的邮件
    CONSTRAINT fk_mail_receiver
        FOREIGN KEY (receiver_id) REFERENCES Users(user_id)   -- 外键：邮件接收者必须是已注册用户
        ON UPDATE CASCADE ON DELETE CASCADE,                    -- 用户ID更新时级联修改；接收者被删除时自动删除其收到的邮件
    CONSTRAINT fk_mail_game
        FOREIGN KEY (game_id) REFERENCES Games(game_id)       -- 外键：邮件关联的游戏必须存在（可为 NULL）
        ON UPDATE CASCADE ON DELETE SET NULL                    -- 游戏ID更新时级联修改；删除游戏时，邮件的 game_id 置为 NULL（保留邮件内容）
) ENGINE=InnoDB;

-- ========== 好友私聊消息表 ==========
-- 好友之间发送的文字或图片消息
CREATE TABLE FriendMessages (
    msg_id INT AUTO_INCREMENT PRIMARY KEY,                      -- 消息ID，自增主键
    sender_id INT NOT NULL,                                     -- 发送者ID（关联 Users）
    receiver_id INT NOT NULL,                                   -- 接收者ID（关联 Users）
    content TEXT NULL,                                          -- 文字内容（文字和图片二选一）
    image_path VARCHAR(255) NULL,                               -- 图片路径
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,    -- 发送时间
    CONSTRAINT fk_fmsg_sender
        FOREIGN KEY (sender_id) REFERENCES Users(user_id)     -- 外键：消息发送者必须是已注册用户
        ON UPDATE CASCADE ON DELETE CASCADE,                    -- 用户ID更新时级联修改；发送者被删除时自动删除其发送的消息
    CONSTRAINT fk_fmsg_receiver
        FOREIGN KEY (receiver_id) REFERENCES Users(user_id)   -- 外键：消息接收者必须是已注册用户
        ON UPDATE CASCADE ON DELETE CASCADE,                    -- 用户ID更新时级联修改；接收者被删除时自动删除发给他的消息
    CONSTRAINT chk_fmsg_content CHECK (                         -- 检查约束：文字和图片不能同时存在，也不能同时为空
        (content IS NOT NULL AND image_path IS NULL) OR
        (content IS NULL AND image_path IS NOT NULL)
    )
) ENGINE=InnoDB;

-- 索引：加速好友间的聊天记录双向查询
CREATE INDEX idx_fmsg_sender_receiver ON FriendMessages(sender_id, receiver_id);
CREATE INDEX idx_fmsg_receiver_sender ON FriendMessages(receiver_id, sender_id);
-- 索引：加速按时间排序聊天记录
CREATE INDEX idx_fmsg_created_at ON FriendMessages(created_at);

-- ============================================================
-- 存储过程、函数、触发器
-- ============================================================


DELIMITER $$

-- ========== 存储过程 1：获取评分最高的 TOP 10 游戏 ==========
-- 用于首页排行榜展示
-- 按平均评分降序排列，评分相同时按评价数降序
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

-- ========== 存储过程 2：按价格排序获取 TOP 10 游戏 ==========
-- 参数 p_desc = 1 表示降序（从高到低），0 表示升序（从低到高）
-- 用于商店页面的价格排序功能
CREATE PROCEDURE GetGamesByPrice(IN p_desc TINYINT)
BEGIN
    IF p_desc = 1 THEN
        -- 降序
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
        -- 升序
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

-- ========== 函数：获取游戏的 Steam 风格评价标签 ==========
-- 根据平均评分返回中文评价描述
-- 参数：p_game_id - 游戏ID
-- 返回值：'暂无评价' / '好评如潮' / '褒贬不一' / '差评如潮'

CREATE FUNCTION GetSteamStatus(p_game_id INT)
RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
    DECLARE v_avg DECIMAL(3,2);          -- 临时变量，存放平均评分
    SELECT avg_rating INTO v_avg FROM Games WHERE game_id = p_game_id;

    IF v_avg IS NULL THEN
        RETURN '暂无评价';                -- 没有评价
    ELSEIF v_avg >= 4.5 THEN
        RETURN '好评如潮';                -- 评分 >= 4.5
    ELSEIF v_avg >= 3.0 THEN
        RETURN '褒贬不一';                -- 评分 3.0 ~ 4.49
    ELSE
        RETURN '差评如潮';                -- 评分 < 3.0
    END IF;
END$$

-- ========== 触发器：评价插入后自动更新游戏评分 ==========
-- 触发时机：每次在 Reviews 表插入新评价后自动执行
-- 功能：重新计算该游戏的平均评分和评价总数，更新到 Games 表

CREATE TRIGGER After_Review_Insert
AFTER INSERT ON Reviews
FOR EACH ROW
BEGIN
    UPDATE Games g
    SET
        -- 重新计算该游戏所有评价的平均分，保留两位小数
        g.avg_rating = (
            SELECT ROUND(AVG(r.rating), 2) FROM Reviews r WHERE r.game_id = NEW.game_id
        ),
        -- 重新统计该游戏的评价总数
        g.review_count = (
            SELECT COUNT(*) FROM Reviews r WHERE r.game_id = NEW.game_id
        )
    WHERE g.game_id = NEW.game_id;
END$$

-- ========== 存储过程 3：获取销量最高的 TOP 10 游戏 ==========
-- 按订单数量统计销量，销量相同时按评分降序
-- 用于首页销量排行榜展示
CREATE PROCEDURE GetTopSellingGames()
BEGIN
    SELECT
        g.game_id,
        g.title,
        g.price,
        g.avg_rating,
        g.review_count,
        g.cover_path,
        COUNT(o.order_id) AS sales_count             -- 统计每个游戏的订单数作为销量
    FROM Games g
    LEFT JOIN Orders o ON o.game_id = g.game_id      -- 左连接：没有订单的游戏也会出现（销量为 0）
    GROUP BY g.game_id, g.title, g.price, g.avg_rating, g.review_count, g.cover_path
    ORDER BY sales_count DESC, g.avg_rating DESC    -- 先按销量降序，再按评分降序
    LIMIT 10;
END$$

-- ========== 存储过程 4：购买游戏（含事务处理） ==========
-- 这是一个带事务的完整购买流程，保证数据一致性
-- 参数：p_user_id - 买家ID，p_game_id - 要购买的游戏ID
-- 功能说明：
--   1. 查询游戏价格和发布者，加行级锁防止并发问题
--   2. 查询买家余额，加行级锁
--   3. 校验：游戏存在、用户存在、未重复购买、余额充足
--   4. 扣买家钱 → 给发布者加钱 → 写入订单
--   5. 任何一步失败则回滚全部操作

CREATE PROCEDURE PurchaseGameTransaction(IN p_user_id INT, IN p_game_id INT)
BEGIN
    -- 声明局部变量
    DECLARE v_price DECIMAL(10,2);          -- 游戏价格
    DECLARE v_balance DECIMAL(10,2);        -- 买家余额
    DECLARE v_publisher_id INT;             -- 游戏发布者ID
    DECLARE v_exists INT DEFAULT 0;         -- 是否已购买标记

    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;                           -- 回滚事务，撤销所有修改
        RESIGNAL;                           -- 把错误继续向上抛，让 Python 端可以捕获
    END;

    START TRANSACTION;                      -- 开始事务

    -- 第 1 步：查询游戏价格和发布者ID，锁定该行防止并发修改
    SELECT price, publisher_id
    INTO v_price, v_publisher_id
    FROM Games
    WHERE game_id = p_game_id
    FOR UPDATE;

    -- 第 2 步：查询买家余额，锁定该行防止并发修改
    SELECT balance INTO v_balance
    FROM Users
    WHERE user_id = p_user_id
    FOR UPDATE;

    -- 第 3 步：四重校验，任何一项不通过就报错回滚
    -- 校验 1：游戏是否存在（如果 v_price 为 NULL，说明没查到该游戏）
    IF v_price IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Game not found';
    END IF;

    -- 校验 2：用户是否存在
    IF v_balance IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'User not found';
    END IF;

    -- 校验 3：是否已经购买过
    SELECT COUNT(*) INTO v_exists
    FROM Orders
    WHERE user_id = p_user_id AND game_id = p_game_id;

    IF v_exists > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Already purchased';
    END IF;

    -- 校验 4：余额是否足够支付
    IF v_balance < v_price THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Insufficient balance';
    END IF;

    -- 第 4 步：执行购买
    -- 扣买家的钱
    UPDATE Users
    SET balance = balance - v_price
    WHERE user_id = p_user_id;

    -- 给发布者加钱
    UPDATE Users
    SET balance = balance + v_price
    WHERE user_id = v_publisher_id;

    -- 记录订单
    INSERT INTO Orders(user_id, game_id, price)
    VALUES (p_user_id, p_game_id, v_price);

    -- 提交事务，所有修改永久生效
    COMMIT;
END$$

-- 恢复分隔符为分号
DELIMITER ;