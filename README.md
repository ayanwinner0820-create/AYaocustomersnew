# AYaocustomers - 部署说明（Streamlit Cloud）

## 准备
1. 在 GitHub 创建仓库（例如：`AYaocustomers`），把本项目文件推上去（main 分支）。
2. 在 GitHub 再创建一个仓库用于备份（例如：`AYaocustomersremark`）。建议设为 Private。

## 在 Streamlit Cloud 部署
1. 登录 https://share.streamlit.io (Streamlit Cloud)，并连接你的 GitHub 账号。
2. New app → 选择你的仓库 `AYaocustomers` → Branch: main → Main file: `app.py` → Deploy。

## 配置 Secrets（非常重要、用于安全备份）
在 Streamlit Cloud 应用的 Settings → Secrets 中添加（不要把 token 放在代码中）：


保存后请点击 Redeploy / Rerun。

## 默认管理员
- 用户名： `admin`
- 密码： `admin123`

首次登录后，请尽快：
- 修改管理员密码（Admin → Reset password）
- 新增团队用户并分配主要负责人

## 自动备份说明
- 管理员登录时，系统会尝试检测并触发备份（如果上次备份 >24h），也可在管理员侧边栏手动触发“Backup now”。
- 备份上传到你设置的 `GITHUB_REPO` 的 `backups/` 目录，文件名含时间戳。

## 使用说明
- 多语言：侧边栏选择语言（会保存在 session 与用户资料）
- 用户权限：普通用户仅能查看/导出自己负责的客户
- 操作日志：仅管理员可见，记录重要操作

## 常见问题
- token 权限不足：确保 PAT 有 `repo` 权限
- 数据库文件：存储在 Streamlit Cloud 的持久存储中（`crm_data.sqlite`）
