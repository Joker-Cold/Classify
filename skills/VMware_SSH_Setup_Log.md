# VMware 虚拟机 SSH 连接配置记录

## 目标

从 Windows CMD 通过 SSH 控制 VMware 虚拟机中的 Innovus EDA 工具。

---

## 环境信息

- **Windows**: Windows 11 Home
- **虚拟机**: VMware, RHEL 6.7 (CentOS 6) x86_64
- **VM用户**: IC（无sudo权限，无密码）
- **Innovus**: `/opt/Cadence/INNOVUS15/bin/innovus` v15.20

---

## 配置步骤

### 1. 获取虚拟机 IP

VM 默认没有分配 IPv4，需要手动获取：

```bash
su -
dhclient eth0
ip addr show eth0
```

获得 IP: `192.168.49.133`

### 2. 确认 SSH 服务运行

```bash
service sshd status
# openssh-daemon (pid 2753) is running...
```

系统使用 SysVinit，没有 `systemctl`，使用 `service` 命令。

### 3. 在 Windows 生成 SSH 密钥

```cmd
ssh-keygen -t rsa -f %USERPROFILE%\.ssh\id_rsa -N ""
```

### 4. 将公钥添加到虚拟机

由于 IC 用户无密码，无法通过 `ssh-copy-id` 传输，改为在虚拟机内手动操作：

```bash
su -
mkdir -p /home/IC/.ssh
vi /home/IC/.ssh/authorized_keys
# 粘贴 Windows 端 ~/.ssh/id_rsa.pub 的内容
chmod 700 /home/IC/.ssh
chmod 600 /home/IC/.ssh/authorized_keys
chown -R IC:IC /home/IC/.ssh
```

### 5. 开启 SSH 公钥认证

```bash
sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/#AuthorizedKeysFile/AuthorizedKeysFile/' /etc/ssh/sshd_config
service sshd restart
```

### 6. 修复 Home 目录权限（关键）

SSH 要求 home 目录权限不超过 755，原来是 777 导致公钥认证失败：

```bash
chmod 755 /home/IC
```

### 7. 连接测试成功

```bash
ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa IC@192.168.49.133 "echo connected && whoami"
# connected
# IC
```

需要加 `-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa` 因为虚拟机 SSH 版本较老。

---

## Screen 共享终端配置

### 安装 Screen

虚拟机 yum 源不可用，通过 RPM 包手动安装：

1. 下载 `screen-4.0.3-19.el6.x86_64.rpm`（从 vault.centos.org）
2. SCP 传到虚拟机：
   ```bash
   scp -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa screen-4.0.3-19.el6.x86_64.rpm IC@192.168.49.133:~/Desktop/
   ```
3. Root 安装：
   ```bash
   rpm -ivh /home/IC/Desktop/screen-4.0.3-19.el6.x86_64.rpm
   ```

### 使用 Screen 共享会话

**Claude 端（通过 SSH）**：
```bash
# 创建 screen 会话
ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa IC@192.168.49.133 "screen -dmS innovus bash"

# 在 screen 中启动 Innovus
ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa IC@192.168.49.133 "screen -S innovus -X stuff \$'cd ~/Desktop && innovus -no_gui\n'"

# 向 Innovus 发送命令
ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa IC@192.168.49.133 "screen -S innovus -X stuff \$'<command>\n'"
```

**用户端（虚拟机终端）**：
```bash
screen -x innovus
```

这样 Claude 和用户共享同一个终端，用户能实时看到所有操作。

---

## 常见问题排障

| 问题 | 解决方案 |
|------|----------|
| VM 重启后无 IP | `su -` → `dhclient eth0` |
| SSH 连接算法不匹配 | 加 `-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa` |
| 公钥认证失败 | 检查 `/home/IC` 权限必须是 755 |
| SELinux 阻止认证 | `setenforce 0` 或 `restorecon -Rv /home/IC/.ssh` |
| IC 无 sudo 权限 | 使用 `su -` 切换 root |
| yum 源不可用 | 手动下载 RPM 包安装 |
