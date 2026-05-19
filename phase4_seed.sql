-- Phase 4 seed data (users only)
-- Password for both users: 123456

USE steam_platform;

DELETE FROM Reviews;
DELETE FROM Orders;
DELETE FROM Games;
DELETE FROM Users;

INSERT INTO Users(username, password_hash, role, balance)
VALUES
  ('player1', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', 'player', 200.00),
  ('publisher1', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', 'publisher', 0.00);
