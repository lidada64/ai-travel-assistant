🚀 一、基础协作规则（必须遵守）
1️⃣ 不要直接往 main 分支推代码

正确流程：

main  ← 稳定版本
  ↑
feature/xxx 分支开发

每个人：

git checkout -b feature/add-flight-search

开发完：

git push origin feature/add-flight-search

然后在 GitHub 上发 Pull Request（PR）

👉 审核通过再合并进 main。

这样可以避免：

覆盖别人代码

把 bug 直接带进主分支

项目崩掉

2️⃣ Commit 要小而清晰，且每写一个功能commit一次！

❌ 不要这样：

update
fix
修改代码

✅ 要这样：

add hotel recommendation module
fix weather api timeout issue
refactor agent workflow structure

规则：

一次 commit 只做一件事

信息写清楚改了什么

3️⃣ 永远 pull 再 push

每天开始工作前：

git pull origin main

否则很容易：

冲突

覆盖别人代码

🧠 二、进阶团队规范（推荐）
4️⃣ 使用分支命名规范

推荐统一格式：

feature/功能名
fix/问题名
refactor/模块名
docs/文档更新

例如：

feature/ai-route-planner
fix/login-bug

项目一大，没有规范会非常混乱。

5️⃣ Pull Request 要写清楚

PR 描述应该写：

做了什么

为什么做

是否影响其他模块

测试结果

示例：

This PR adds flight search functionality using Amadeus API.
Tested with 5 sample routes.
No breaking changes.
6️⃣ Code Review 规则

团队里至少：

1 个人 review

才允许 merge

Review 关注：

是否有重复代码

是否影响现有逻辑

命名是否清晰

是否符合项目结构

这一步会极大提升项目质量。

📁 三、项目结构统一（非常重要）

你做 AI 旅游助手这类项目，建议结构：

ai-travel-assistant/
│
├── app/
│   ├── agent/
│   ├── tools/
│   ├── services/
│
├── tests/
├── requirements.txt
├── .gitignore
└── README.md

不要：

main.py
main2.py
test_new.py
final_version.py
final_version_v2.py

那是灾难 😄

⚠️ 四、绝对禁止的行为

❌ 不写 .gitignore

❌ 把 venv 提交上去

❌ 强制 push（git push -f）

❌ 直接改 main

❌ 不写 commit message

每写一个功能 commit 一次！

fork完成之后：

建议安装虚拟环境并激活：
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
安装依赖：
```bash
pip install -r requirements.txt
```

很多API可以在https://serpapi.com/google-images-api 中获取
