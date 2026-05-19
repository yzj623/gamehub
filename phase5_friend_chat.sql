-- Phase 5: Friend Chat (private messaging between friends)
USE steam_platform;

CREATE TABLE IF NOT EXISTS FriendMessages (
    msg_id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT NOT NULL,
    receiver_id INT NOT NULL,
    content TEXT NULL,
    image_path VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fmsg_sender
        FOREIGN KEY (sender_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_fmsg_receiver
        FOREIGN KEY (receiver_id) REFERENCES Users(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_fmsg_content CHECK (
        (content IS NOT NULL AND image_path IS NULL) OR
        (content IS NULL AND image_path IS NOT NULL)
    )
) ENGINE=InnoDB;

CREATE INDEX idx_fmsg_sender_receiver ON FriendMessages(sender_id, receiver_id);
CREATE INDEX idx_fmsg_receiver_sender ON FriendMessages(receiver_id, sender_id);
CREATE INDEX idx_fmsg_created_at ON FriendMessages(created_at);
