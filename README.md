# 🍰 XOTD — X of the Day

> 每天一条知识,学习、发现并与世界分享。
> A community for sharing one piece of knowledge a day — learn, discover, and share.

XOTD 是一个轻量的「每日知识卡片」社区:任何人都能分享一个单词、概念或自定义词条,系统自动生成中英双语对照,所有人都能浏览、检索、点赞与收藏式复习。界面走「克制的高级感」路线(暖白 / 深炭灰双主题、衬线标题、丝滑动效),并完整适配移动端。

---

## ✨ 功能特性

**内容与学习**
- 📇 **每日知识卡片** — 单词 / 概念 / 自定义类型,首页展示当日精选
- 🌐 **中英双语** — 提交后由后台自动翻译,一键切换显示语言
- 🏷️ **多标签** — 每条词条可打多个标签,点击标签即可筛选
- 🎴 **Flashcard 翻转复习** — 正面词、背面释义,支持翻面 / 上一张下一张 / 乱序 / 键盘操作
- 🔍 **后端搜索 + 无限滚动** — 按关键词、标签、类型、日期检索,滚动自动加载更多
- 📎 **附件与在线查看** — 上传图片 / Markdown / txt / PDF,站内直接预览(Markdown 渲染并消毒)

**社区与个人**
- 👤 **账户系统** — 邮箱验证码注册、登录
- 🖼️ **个人头像** — 上传 / 更换 / 移除,显示在导航、卡片署名与个人主页
- 🪪 **用户主页** — 展示头像、加入时间、贡献数与全部实名词条;点击作者名即可访问
- 🔥 **连续贡献 streak** — 记录连续产出知识的天数
- ❤️ **点赞** — 为喜欢的词条点赞
- ✏️ **自助维护** — 作者可编辑 / 删除自己的词条,管理员保留全站管理权限
- 📬 **每日邮件订阅** — 每天把当日精选发到邮箱(可在设置页开关)

**体验**
- 🌗 浅色 / 深色双主题,平滑切换并记忆偏好
- 🎞️ 统一缓动曲线的入场 / 滚动 / 微交互动效,尊重 `prefers-reduced-motion`
- 📱 完整移动端适配与触摸交互
- 🌍 界面中英文切换(i18n)

---

## 🛠️ 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python · [Flask](https://flask.palletsprojects.com/) |
| 数据库 | SQLite |
| 前端 | 原生 HTML + CSS + JavaScript(无构建步骤),CSS 变量驱动的设计系统 |
| 翻译 | [deep-translator](https://pypi.org/project/deep-translator/)(Google 翻译,后台异步执行) |
| 邮件 | 网易 163 SMTP(注册验证码 + 每日精选) |
| 部署 | Azure Web App + GitHub Actions 自动部署 |

---

## 🚀 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量(见下)——本地最少可不配,使用默认值
cp .env.example .env

# 3. 启动
python app.py
# 打开 http://127.0.0.1:5000
```

首次运行会自动创建 / 升级 `xotd.db`(无需手动迁移)。

---

## 🔑 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `SECRET_KEY` | Flask session 密钥,**生产环境务必设置** | 生产必需 |
| `NETEASE_EMAIL` / `NETEASE_PASSWORD` | 网易 163 邮箱与授权码,用于发送验证码与每日邮件 | 邮件功能需要 |
| `CRON_SECRET` | 保护 `/cron/daily-digest` 定时接口的密钥 | 每日邮件需要 |
| `SITE_URL` | 站点对外地址(用于邮件内的链接) | 可选 |
| `FLASK_DEBUG` | 本地调试开关,设 `0` 关闭 | 可选 |

> 上传的附件本地存于 `uploads/`,Azure 上存于持久化目录 `/home/uploads`。

---

## ⏰ 每日邮件(可选)

每日精选邮件由定时任务触发:

1. 在 Azure Web App 设置环境变量 `CRON_SECRET`(任意随机字符串)。
2. 在 GitHub 仓库 `Settings → Secrets` 添加同名 `CRON_SECRET`(可选 `SITE_BASE_URL`)。
3. [`.github/workflows/daily-digest.yml`](.github/workflows/daily-digest.yml) 会按计划调用受保护的 `/cron/daily-digest` 接口,向所有订阅用户群发当日词条。

---

## 📁 项目结构

```
xotd/
├── app.py                  # Flask 应用:路由、API、数据库、邮件
├── requirements.txt
├── templates/
│   ├── base.html           # 布局、导航、主题切换
│   ├── _card.html          # 共享卡片组件(首页 / 发现 / 主页 / 搜索接口复用)
│   ├── index.html          # 首页(今日精选)
│   ├── explore.html        # 发现页(搜索 / 筛选 / 无限滚动)
│   ├── flashcards.html     # 记忆卡翻转
│   ├── user.html           # 用户主页
│   ├── settings.html       # 头像与订阅设置
│   ├── submit.html         # 提交 / 编辑词条
│   ├── login.html / register.html
│   └── viewer.html         # 附件在线查看
├── static/
│   ├── css/style.css       # 设计系统(CSS 变量、双主题、动效)
│   └── js/main.js          # i18n、主题、搜索、点赞、上传、Flashcard 等
└── .github/workflows/      # 部署 + 每日邮件定时任务
```

---

## 📄 License

© 2026 XOTD. All rights reserved.
