"""凭证与 token 的本地安全存储。

- env 文件：~/.config/etsy-automation/env，KEY=VALUE 每行一个，权限 600。
  需要的键：ETSY_CLIENT_ID（= API keystring）、ETSY_SHARED_SECRET、
            ETSY_REDIRECT_URI；可选 ETSY_CLIENT_SECRET、ETSY_TOKEN_URL、
            ETSY_SHOP_NAME、ETSY_TAXONOMY_ID。
- token 文件：~/.config/etsy-automation/tokens.json，权限 600。
"""
import json
import os
import stat

CONFIG_DIR = os.path.expanduser("~/.config/etsy-automation")


def _ensure_dir():
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)


def _token_path(filename="tokens.json"):
    return os.path.join(CONFIG_DIR, filename)


def load_env():
    """读 env 文件。文件不存在返回空 dict（调用方决定缺什么就报错）。"""
    path = os.path.join(CONFIG_DIR, "env")
    env = {}
    if not os.path.exists(path):
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def save_tokens(tokens, filename="tokens.json"):
    """保存 token dict，强制 600 权限。"""
    _ensure_dir()
    path = _token_path(filename)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(tokens, f)
    except Exception:
        os.close(fd)
        raise
    os.chmod(path, 0o600)
    # 二次确认权限
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode != 0o600:
        raise RuntimeError(f"token 文件权限异常: {oct(mode)}")


def load_tokens(filename="tokens.json"):
    path = _token_path(filename)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def write_env_template():
    """生成 env 模板文件（不含任何真实值），方便主 agent 指导用户填写。"""
    _ensure_dir()
    path = os.path.join(CONFIG_DIR, "env")
    if os.path.exists(path):
        print(f"env 已存在：{path}，不覆盖")
        return
    template = (
        "# Etsy automation credentials — 600 权限，仅本机可读\n"
        "# 由主 agent 经安全流程填入真实值，不要提交到任何仓库\n"
        "ETSY_CLIENT_ID=\n"
        "ETSY_SHARED_SECRET=\n"
        "# 回调：Etsy 只接受 https+真实域名（2026-09-20 起拒绝 localhost/IP）；\n"
        "# 一次性方案可用 https://webhook.site/<uuid>\n"
        "ETSY_REDIRECT_URI=\n"
        "# 可选：ETSY_CLIENT_SECRET=   # refresh 实测不需要传，不要设\n"
        "# 可选：ETSY_TOKEN_URL=https://api.etsy.com/v3/public/oauth/token\n"
        "# 可选：ETSY_SHOP_NAME=ZenPixelWalls\n"
        "# 可选：ETSY_TAXONOMY_ID=\n"
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(template)
    print(f"已生成模板：{path}（600 权限），请填入真实值")


if __name__ == "__main__":
    write_env_template()
