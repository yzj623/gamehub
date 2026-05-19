# Game Hub - 游戏发行与交易平台

## 部署到服务器完整教程

---

### 一、服务器环境准备

#### 1. 安装 Python 3.10+
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv -y

# CentOS/RHEL
sudo yum install python3 python3-pip -y
```

#### 2. 安装 MySQL 8.0+
```bash
# Ubuntu/Debian
sudo apt install mysql-server -y

# CentOS/RHEL
sudo yum install mysql-server -y
```

#### 3. 安装 Git（可选，用于拉取代码）
```bash
sudo apt install git -y
```

---

### 二、MySQL 数据库配置

#### 1. 设置 MySQL root 密码

安装 MySQL 后，先登录（刚安装时可能无需密码）：

```bash
sudo mysql
```

在 MySQL 命令行中执行：

```sql
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '你的强密码';
FLUSH PRIVILEGES;
EXIT;
```

> ⚠️ **密码安全建议**：
> - 密码长度至少 16 位
> - 包含大小写字母、数字和特殊字符
> - 例如：`GameHub_2024_Secure!Pass`
> - **不要使用** `123456`、`password` 等弱密码

#### 2. 创建专用数据库用户（推荐）

用新密码重新登录：

```bash
mysql -u root -p
```

创建专用用户：

```sql
-- 创建专用用户（不要直接用 root）
CREATE USER 'gamehub'@'localhost' IDENTIFIED BY 'GameHub_2024_Secure!Pass';

-- 授予权限（注意：数据库 game_hub 不需要手动创建，程序会自动创建）
GRANT ALL PRIVILEGES ON game_hub.* TO 'gamehub'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

> 🔐 **为什么创建专用用户？**
> - 避免使用 root 账号，降低安全风险
> - 可以单独控制权限
> - 方便后续数据库迁移和管理

#### 3. 验证用户创建成功

```bash
mysql -u gamehub -p -e "SELECT 1"
```

输入密码后能正常连接即可。

> ✅ **不需要手动导入 SQL 文件！** `start_server.py` 启动时会自动完成以下操作：
> 1. 检查数据库 `game_hub` 是否存在，不存在则自动创建
> 2. 检查数据库中是否有表，如果为空则自动导入 `phase1_schema.sql`
> 3. 如果存在 `phase5_friend_chat.sql` 也会自动导入
> 4. 如需导入测试数据，设置环境变量 `SEED_DATA=1` 即可自动导入 `phase4_seed.sql`


---

### 三、上传项目文件

#### 方式一：使用 Git（推荐）

```bash
# 在服务器上创建项目目录
mkdir -p /var/www/gamehub
cd /var/www/gamehub

# 克隆代码（替换为你的仓库地址）
git clone https://github.com/你的用户名/gamehub.git .
```

#### 方式二：使用 SCP 上传

在本地电脑上：

```bash
# 将整个项目打包
tar -czf gamehub.tar.gz -C /path/to/SQLwork .

# 上传到服务器
scp gamehub.tar.gz 你的用户名@服务器IP:/var/www/gamehub/

# 在服务器上解压
ssh 你的用户名@服务器IP
cd /var/www/gamehub
tar -xzf gamehub.tar.gz
```

#### 方式三：使用 FTP/FileZilla

1. 在本地将 `SQLwork` 文件夹整个上传到服务器
2. 推荐放在 `/var/www/gamehub/` 目录

---

### 四、配置项目

#### 1. 创建虚拟环境

```bash
cd /var/www/gamehub
python3 -m venv venv
source venv/bin/activate
```

#### 2. 安装依赖

```bash
pip install -r requirements.txt
```

#### 3. 配置环境变量

创建 `.env` 文件（或直接在系统环境变量中设置）：

```bash
# 方法一：创建 .env 文件（推荐）
cat > .env << 'EOF'
# 数据库配置
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=gamehub
DB_PASSWORD=GameHub_2024_Secure!Pass
DB_NAME=game_hub
DB_POOL_SIZE=5

# Flask 配置
SECRET_KEY=your-very-long-random-secret-key-here
FLASK_PORT=5000

# 上传目录（默认在项目 static/uploads 下）
# UPLOAD_DIR=/var/www/gamehub/static/uploads
EOF
```

> 🔑 **SECRET_KEY 生成建议**：
> ```bash
> python3 -c "import secrets; print(secrets.token_hex(32))"
> ```
> 将输出的随机字符串设为 `SECRET_KEY`

#### 4. 创建上传目录

```bash
mkdir -p static/uploads
chmod 755 static/uploads
```

---

### 五、启动服务

#### 1. 直接启动（测试用）

```bash
cd /var/www/gamehub
source venv/bin/activate

# 加载环境变量
export $(grep -v '^#' .env | xargs)

# 启动
python start_server.py
```

访问 `http://服务器IP:5000` 即可看到网站。

#### 2. 使用 systemd 作为系统服务（推荐，开机自启）

创建服务文件：

```bash
sudo nano /etc/systemd/system/gamehub.service
```

写入以下内容：

```ini
[Unit]
Description=Game Hub Web Application
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/gamehub
EnvironmentFile=/var/www/gamehub/.env
ExecStart=/var/www/gamehub/venv/bin/python start_server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable gamehub
sudo systemctl start gamehub
sudo systemctl status gamehub
```

常用命令：

```bash
sudo systemctl restart gamehub   # 重启
sudo systemctl stop gamehub      # 停止
sudo journalctl -u gamehub -f    # 查看日志
```

---

### 六、使用 Nginx 反向代理（可选，推荐生产环境）

#### 1. 安装 Nginx

```bash
sudo apt install nginx -y
```

#### 2. 配置 Nginx

```bash
sudo nano /etc/nginx/sites-available/gamehub
```

```nginx
server {
    listen 80;
    server_name 你的域名或IP;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/gamehub/static/;
        expires 7d;
    }
}
```

#### 3. 启用站点

```bash
sudo ln -s /etc/nginx/sites-available/gamehub /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 4. 配置 HTTPS（使用 Let's Encrypt）

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d 你的域名
```

---

### 七、防火墙配置

```bash
# Ubuntu UFW
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw enable

# 如果直接使用 Flask 端口
sudo ufw allow 5000/tcp
```

---

### 八、常见问题

#### Q1: 数据库连接失败
```
pymysql.err.OperationalError: (1045, "Access denied for user 'gamehub'@'localhost'")
```
**解决**：检查 `.env` 文件中的 `DB_USER` 和 `DB_PASSWORD` 是否正确。

#### Q2: 数据库不存在
```
pymysql.err.OperationalError: (1049, "Unknown database 'game_hub'")
```
**解决**：登录 MySQL 创建数据库：
```sql
CREATE DATABASE IF NOT EXISTS game_hub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

#### Q3: 端口被占用
```
OSError: [Errno 98] Address already in use
```
**解决**：修改端口或杀死占用进程：
```bash
# 修改端口
export FLASK_PORT=5001
python start_server.py

# 或杀死占用进程
sudo lsof -i :5000
sudo kill -9 PID
```

#### Q4: 上传文件权限问题
```
PermissionError: [Errno 13] Permission denied: 'static/uploads/...'
```
**解决**：
```bash
sudo chown -R www-data:www-data /var/www/gamehub/static/uploads
sudo chmod -R 755 /var/www/gamehub/static/uploads
```

#### Q5: 如何修改数据库密码？

1. 在 MySQL 中修改密码：
```sql
ALTER USER 'gamehub'@'localhost' IDENTIFIED BY '新密码';
FLUSH PRIVILEGES;
```

2. 更新 `.env` 文件中的 `DB_PASSWORD`

3. 重启服务：
```bash
sudo systemctl restart gamehub
```

---

### 九、安全建议

1. **MySQL 安全**
   - 使用强密码（16位以上，含特殊字符）
   - 创建专用数据库用户，不要用 root
   - 定期备份数据库：`mysqldump -u gamehub -p game_hub > backup.sql`

2. **Flask 安全**
   - 设置强 `SECRET_KEY`
   - 生产环境关闭 `debug=True`
   - 使用 Nginx 反向代理 + HTTPS

3. **服务器安全**
   - 仅开放必要端口（22, 80, 443）
   - 定期更新系统：`sudo apt update && sudo apt upgrade`
   - 使用 fail2ban 防止暴力破解

---

### 十、默认测试账号（如果导入了 phase4_seed.sql）

| 角色   | 用户名     | 密码   |
| ------ | ---------- | ------ |
| 玩家   | player1    | 123456 |
| 发行商 | publisher1 | 123456 |

> ⚠️ 生产环境请删除或修改这些测试账号的密码！
