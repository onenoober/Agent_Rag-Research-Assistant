# Git 企业使用完整指南

> 适合新手学习的企业级 Git 工作流程与最佳实践

---

## 目录

1. [Git 基础概念回顾](#1-git-基础概念回顾)
2. [企业常用分支策略](#2-企业常用分支策略)
3. [日常开发完整流程](#3-日常开发完整流程)
4. [企业真实案例：电商订单系统](#4-企业真实案例电商订单系统)
5. [常见问题与解决方案](#5-常见问题与解决方案)
6. [Git 钩子与自动化](#6-git-钩子与自动化)
7. [安全与权限管理](#7-安全与权限管理)

---

## 1. Git 基础概念回顾

### 1.1 工作区、暂存区与版本库

```
┌─────────────────────────────────────────────────────────────┐
│                        工作区 (Working Directory)           │
│   你正在编辑的文件，这些文件还没有被 Git 跟踪               │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ git add
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      暂存区 (Staging Area / Index)          │
│   准备提交的文件快照，Git 知道这些文件要进入下一版本         │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ git commit
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      本地版本库 (.git directory)             │
│   所有的版本历史都在这里，包含完整的提交记录                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ git push
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      远程版本库 (Remote Repository)         │
│   GitHub / GitLab / Gitee 等服务器上的共享仓库              │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心命令速查表

```bash
# ============================================
# 基础配置
# ============================================

# 设置用户信息（必须，每个提交都会记录）
git config --global user.name "张三"
git config --global user.email "zhangsan@company.com"

# 查看所有配置
git config --list

# 生成 SSH 密钥（用于连接远程仓库）
ssh-keygen -t ed25519 -C "zhangsan@company.com"


# ============================================
# 仓库操作
# ============================================

# 克隆远程仓库
git clone git@github.com:company/project.git

# 初始化新仓库
git init

# 添加远程仓库
git remote add origin git@github.com:company/project.git


# ============================================
# 日常工作流程
# ============================================

# 查看当前状态
git status

# 查看修改内容
git diff              # 工作区 vs 暂存区
git diff HEAD         # 工作区 vs 最新提交
git diff --staged     # 暂存区 vs 最新提交

# 添加文件到暂存区
git add filename.txt           # 添加单个文件
git add src/                    # 添加整个目录
git add .                       # 添加所有修改
git add -p                      # 交互式添加（选择性地添加部分修改）

# 提交到本地仓库
git commit -m "提交信息：简明描述这次做了什么"
git commit -am "提交信息"        # 快捷方式：add + commit（仅适用于已跟踪文件）

# 推送到远程仓库
git push origin branch-name
git push -u origin branch-name  # 首次推送，设置上游分支


# ============================================
# 分支操作
# ============================================

# 查看分支
git branch                       # 本地分支
git branch -r                    # 远程分支
git branch -a                    # 所有分支

# 创建分支
git branch feature/login          # 基于当前分支创建新分支
git checkout -b feature/login    # 创建并切换

# 切换分支
git checkout main
git switch main                  # 现代写法

# 合并分支
git merge feature/login

# 删除分支
git branch -d feature/login       # 安全删除
git branch -D feature/login       # 强制删除


# ============================================
# 历史与日志
# ============================================

# 查看提交历史
git log
git log --oneline                # 简洁一行
git log --graph                  # 图形化显示分支
git log -n 5                     # 最近5条

# 查看某次提交的内容
git show commit-id

# 查看文件历史
git log --follow filename.txt


# ============================================
# 撤销与回退
# ============================================

# 撤销工作区的修改（恢复到暂存区/最新提交状态）
git checkout -- filename.txt
git restore filename.txt         # 现代写法

# 取消暂存（从暂存区移回工作区）
git reset HEAD filename.txt
git restore --staged filename.txt

# 回退到某个提交（慎用！）
git reset --soft HEAD~1          # 保留修改在暂存区
git reset --mixed HEAD~1         # 保留修改在工作区（默认）
git reset --hard HEAD~1          # 丢弃所有修改（危险！）

# 创建反向提交（不改变历史）
git revert commit-id


# ============================================
# 远程仓库操作
# ============================================

# 拉取代码
git fetch origin                 # 获取远程更新（不合并）
git pull origin main             # 拉取并合并

# 设置远程仓库
git remote set-url origin new-url
git remote -v                   # 查看远程仓库信息
```

---

## 2. 企业常用分支策略

### 2.1 三种主流分支模型对比

```
┌─────────────────┬──────────────────┬──────────────────┬──────────────────┐
│     特性        │     Git Flow     │   GitHub Flow   │ Trunk-Based     │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ 适用团队规模    │ 大型团队/版本发布 │ 中小型团队      │ DevOps/敏捷团队 │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ 分支数量        │ 5-6个长期分支     │ 1-2个长期分支    │ 1个主干分支     │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ 发布方式        │ 通过发布分支      │ 直接从 main 发布 │ 持续部署        │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ 复杂度          │ 高               │ 低              │ 中              │
├─────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ 典型用户        │ 传统软件公司      │ 互联网公司      │ 互联网/SaaS     │
└─────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

### 2.2 Git Flow 详解（适合大型企业/传统软件）

```
                            ┌─hotfix─┐
                           ╱    │      ╲
                          ╱     │       ╲
              ┌──────────┐       │       └──────────┐
              │  release │◄──────┴─────────►───────│
              │   1.0.0  │                       │   release
              └────┬─────┘                       │   1.1.0
                   │                             └────┬─────┐
                   │                                  │     │
         ┌─────────┴─────────┐              ┌─────────┴─────┴─────┐
         │                   │              │                   │
         ▼                   ▼              ▼                   ▼
    ┌─────────┐         ┌─────────┐    ┌─────────┐         ┌─────────┐
    │ develop │         │ develop │    │ develop │         │ develop │
    └────┬────┘         └────┬────┘    └────┬────┘         └────┬────┘
         │                   │              │                   │
    ┌────┴────┐         ┌────┴────┐    ┌────┴────┐         ┌────┴────┐
    │ feature │         │ feature │    │ feature │         │ feature │
    │   /login│         │  /cart  │    │ /search │         │ /pay    │
    └─────────┘         └─────────┘    └─────────┘         └─────────┘
                              ▲
                              │
                        ┌─────────┐
                        │  main   │  ← 生产环境代码（始终可发布）
                        └─────────┘
```

**分支说明：**

| 分支类型 | 命名规则 | 用途 | 生命周期 |
|---------|---------|------|---------|
| `main` | `main` 或 `master` | 生产环境代码 | 永久 |
| `develop` | `develop` | 开发主分支，集成所有功能 | 永久 |
| `feature/*` | `feature/功能名` | 开发新功能 | 功能完成后退化 |
| `release/*` | `release/版本号` | 准备发布版本 | 发布后退化 |
| `hotfix/*` | `hotfix/问题描述` | 紧急修复生产问题 | 修复后退化 |

### 2.3 GitHub Flow 详解（适合互联网公司）

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                            main                                 │
    │  ●────●────●────●────●────●────●────●────●────●                │
    │                                               │                 │
    │                                    ┌──────────┴──────────┐     │
    │                                    │                     ▼     │
    │                                    │              feature/login│
    │                                    │                  ●──●──●─│
    │                                    │                     │      │
    │                                    │            ┌────────┘      │
    │                                    │            │               │
    │                                    │            ▼               │
    │                                    │         Pull Request       │
    │                                    │     (代码审查 + 讨论)      │
    │                                    │            │               │
    │                                    │     审查通过 ─┤             │
    │                                    │            ▼               │
    │                                    │        合并到 main         │
    │                                    │            │               │
    │                                    │            ▼               │
    │                                    │        自动部署             │
    │                                    └────────────────────────────│
    └─────────────────────────────────────────────────────────────────┘
```

### 2.4 Trunk-Based Development（适合 DevOps/持续交付）

```
    main (trunk)
    ●────●────●────●────●────●────●────●────●────●────●────●
         │         │              │              │
         ▼         ▼              ▼              ▼
    feature/a  feature/b      feature/c      feature/d
       ●──●       ●              ●──●           ●
         │        │               │              │
         └────────┴───────┬──────┴──────────────┘
                           │
                           ▼
                      合并回 main
                      
    规则：
    - 分支寿命 < 1 天（最好几小时）
    - 发布从 main 直接打 tag
    - 用 feature flag 控制未完成功能
```

---

## 3. 日常开发完整流程

### 3.1 新功能开发流程（以 GitHub Flow 为例）

```bash
# ============================================
# 场景：张三要在订单系统中添加「订单导出Excel」功能
# ============================================

# ---- 第1步：确保本地 main 是最新的 ----
git checkout main
git pull origin main

# ---- 第2步：创建功能分支 ----
git checkout -b feature/order-export-excel

# ---- 第3步：开始开发，写代码 ----
# ... 编写代码 ...

# ---- 第4步：频繁提交（每完成一个小功能就提交） ----
git status
git add src/services/export_service.py
git commit -m "feat: 创建导出服务基础结构"

git add src/controllers/export_controller.py
git commit -m "feat: 添加导出控制器"

git add tests/test_export.py
git commit -m "test: 添加导出功能单元测试"

# ---- 第5步：推送分支到远程 ----
git push -u origin feature/order-export-excel

# ---- 第6步：在 GitHub/GitLab 创建 Pull Request ----
# 访问 https://github.com/company/order-system/pull/new/feature/order-export-excel

# ---- 第7步：等待代码审查，可能需要修改 ----
git add .
git commit -m "fix: 根据审查意见优化代码"
git push origin feature/order-export-excel

# ---- 第8步：PR 合并后，清理本地分支 ----
git checkout main
git pull origin main
git branch -d feature/order-export-excel
```

### 3.2 修复 Bug 流程

```bash
# ---- 从 main 创建 bugfix 分支 ----
git checkout main
git pull origin main
git checkout -b hotfix/order-null-pointer

# ---- 修复并测试 ----
# ... 修复代码 ...

git add .
git commit -m "fix: 修复订单查询空指针异常"

# ---- 如果是紧急 hotfix，通知团队 ----
git push -u origin hotfix/order-null-pointer

# ---- 创建 PR 进行审查 ----
# 即使是 hotfix，也建议有人审查

# ---- 合并后清理 ----
git checkout main
git pull origin main
git branch -d hotfix/order-null-pointer
```

### 3.3 合并冲突处理

```bash
# ============================================
# 场景：你的 feature 分支与 main 分支产生冲突
# ============================================

# 1. 确保你在 feature 分支上
git status
# 你应该在: feature/order-export

# 2. 切换到 main，拉取最新代码
git checkout main
git pull origin main

# 3. 切回 feature 分支
git checkout feature/order-export

# 4. 将 main 合并到 feature（推荐）或反过来
git merge main

# ============================================
# 如果有冲突，会看到类似输出：
# ============================================
# Auto-merging src/order.py
# CONFLICT (content): Merge conflict in src/order.py
# Automatic merge failed; fix conflicts and then commit the result.

# 5. 查看冲突文件
git status
# 冲突文件会显示为：both modified: src/order.py

# 6. 打开文件，冲突标记如下：
# <<<<<<< HEAD
# 你的代码（main 分支的版本）
# =======
# 别人的代码（feature 分支的版本）
# >>>>>>> feature/order-export

# 7. 手动解决冲突（保留正确的版本）
# 删除不需要的部分，保留需要的代码

# 例如，解决后：
def get_order(order_id):
    order = db.query(Order).filter_by(id=order_id).first()
    # 保留这个新的处理逻辑
    if order is None:
        return {"error": "订单不存在"}
    return order.to_dict()

# 8. 标记冲突已解决
git add src/order.py

# 9. 完成合并提交
git commit -m "merge: 合并 main 分支，解决冲突"

# 10. 推送
git push origin feature/order-export
```

### 3.4 代码回退场景

```bash
# ============================================
# 场景 1：提交了代码但还没 push，想重新组织提交信息
# ============================================
git commit -m "temp: 临时提交"
# 发现写错了，想改
git commit --amend -m "feat: 添加用户登录功能"

# ============================================
# 场景 2：提交了代码但还没 push，想修改文件
# ============================================
git commit -m "feat: 添加用户登录功能"
# 发现有个文件漏了

git add forgotten_file.py
git commit --amend  # 会打开编辑器，可以修改提交信息

# ============================================
# 场景 3：需要回退到之前的某个提交（还没 push）
# ============================================
# 查看提交历史
git log --oneline
# a1b2c3d (HEAD) feat: 添加用户登录功能
# e4f5g6h feat: 添加用户模块
# i7j8k9l init: 初始化项目

# 软回退（保留修改在暂存区）
git reset --soft HEAD~1
# 现在修改在暂存区，可以重新提交

# 混合回退（保留修改在工作区）
git reset --mixed HEAD~1
# 需要重新 add 和 commit

# 硬回退（丢弃所有修改，危险！）
git reset --hard HEAD~1
# 所有修改都没了，谨慎使用！

# ============================================
# 场景 4：已经 push 了代码，发现有问题
# ============================================
# 方案 A：创建反向提交（推荐，不会改变历史）
git revert HEAD
# 这会创建一个新的提交，撤销之前的修改
git push origin branch-name

# 方案 B：如果必须回退（需要团队同意）
git reset --hard HEAD~1
git push --force origin branch-name
# ⚠️ 注意：force push 会重写历史，必须确保没人基于你的提交开发
```

---

## 4. 企业真实案例：电商订单系统

### 4.1 项目背景

```
项目名称：E-Shop 电商订单系统
团队规模：12 人开发团队
技术栈：Java Spring Boot + MySQL + Redis + RabbitMQ
发布时间：每两周一个迭代版本

团队角色：
- 产品经理 1 人
- 前端开发 3 人
- 后端开发 6 人  
- 测试工程师 2 人
```

### 4.2 分支策略选择

**采用 Git Flow 模型**，原因：
1. 有固定版本发布周期
2. 需要维护多个线上版本
3. 有专门的测试环节
4. 团队规模较大，需要清晰的分支管理

```
分支结构：
main           ─ 生产环境
develop        ─ 开发主分支
release/1.0.0  ─ 准备发布
feature/*      ─ 功能开发
hotfix/*       ─ 紧急修复
```

### 4.3 团队成员与职责

| 角色 | 姓名 | 负责模块 |
|------|------|----------|
| 后端负责人 | 李四 | 架构设计、技术决策 |
| 开发工程师 | 王五 | 订单模块 |
| 开发工程师 | 赵六 | 支付模块 |
| 开发工程师 | 钱七 | 用户模块 |
| 测试负责人 | 孙八 | 质量把控 |
| 运维工程师 | 周九 | 部署与监控 |

### 4.4 Sprint 1 开发过程

#### 第一天：Sprint 启动

```bash
# 李四（后端负责人）：初始化 Sprint
git checkout develop
git pull origin develop
git checkout -b release/1.0.0
git push -u origin release/1.0.0

# 团队同步：所有人都从 release/1.0.0 创建自己的功能分支

# 王五：订单模块
git checkout -b feature/order-query release/1.0.0
git push -u origin feature/order-query

# 赵六：支付模块
git checkout -b feature/payment-integration release/1.0.0
git push -u origin feature/payment-integration

# 钱七：用户模块
git checkout -b feature/user-profile release/1.0.0
git push -u origin feature/user-profile
```

#### 第三天：王五完成订单查询功能

```bash
# 王五的工作
git add src/main/java/com/eshop/order/OrderController.java
git commit -m "feat: 订单列表查询接口

- 支持按状态筛选
- 支持分页查询
- 添加查询缓存"

git add src/main/java/com/eshop/order/OrderService.java
git commit -m "feat: 订单服务层实现

- 添加缓存逻辑
- 优化查询性能"

git add src/test/java/com/eshop/order/OrderServiceTest.java
git commit -m "test: 订单服务单元测试

- 测试查询逻辑
- 测试缓存命中"

git add pom.xml
git commit -m "chore: 添加缓存依赖"

# 推送功能分支
git push origin feature/order-query

# 创建 Pull Request
# PR 标题：feat: 订单查询功能开发
# PR 描述：
# ## 功能说明
# 实现了订单列表查询功能，支持状态筛选和分页
# 
# ## 变更内容
# - OrderController 新增 /api/orders 接口
# - OrderService 添加缓存逻辑
# 
# ## 测试情况
# - 单元测试通过
# - 本地接口测试通过
```

#### 第五天：代码审查

```
审查者：赵六（支付模块同事）

审查意见：
1. 分页参数建议使用 PageRequest 对象统一处理
2. 缓存 key 建议添加版本号，方便后续更新
3. 建议添加接口文档注解

王五修改后回复：
1. 已修改为 PageRequest
2. 已添加版本号到缓存 key
3. 已添加 Swagger 注解

审查通过，赵六 approve PR
```

```bash
# 王五：根据审查意见修改
git add .
git commit -m "refactor: 根据审查意见优化代码

- 使用 PageRequest 统一分页参数
- 缓存 key 添加版本号
- 添加 Swagger 接口文档"

git push origin feature/order-query

# 等待所有审查通过后，李四合并代码
# 王五无需操作，等待合并通知
```

#### 第七天：功能合并到 release

```bash
# 李四（后端负责人）：合并王五的订单功能
git checkout release/1.0.0
git pull origin release/1.0.0
git merge origin/feature/order-query

# 解决可能的冲突
# ...

git push origin release/1.0.0
```

#### Sprint 结束时：发布版本

```bash
# 李四：准备发布
git checkout release/1.0.0
git pull origin release/1.0.0

# 确保所有功能都已合并
git log --oneline
# 应该看到所有功能的提交

# 合并到 main
git checkout main
git pull origin main
git merge release/1.0.0

# 打标签
git tag -a v1.0.0 -m "版本 1.0.0 发布

功能列表：
- 订单查询功能
- 支付集成功能
- 用户资料功能

发布时间：2024-01-15"

# 推送 main 和 tag
git push origin main
git push origin v1.0.0

# 合并回 develop
git checkout develop
git merge main
git push origin develop

# 删除 release 分支
git branch -d release/1.0.0
git push origin --delete release/1.0.0
```

### 4.5 紧急 Bug 修复场景

**场景：Sprint 1 发布后第二天，用户反馈订单支付成功但状态未更新**

```bash
# 周九（运维）：发现并报告问题
# 立即通知相关人员创建 hotfix

# 李四：创建 hotfix 分支
git checkout main  # 从 main 创建，而不是 develop
git pull origin main
git checkout -b hotfix/order-payment-status-bug
git push -u origin hotfix/order-payment-status-bug

# 王五：立即开始修复
# ... 定位问题：RabbitMQ 消息消费失败 ...

git add src/main/java/com/eshop/order/PaymentConsumer.java
git commit -m "fix: 修复支付状态更新失败问题

问题原因：RabbitMQ 消费者未正确处理异常
解决方案：添加重试机制和死信队列

影响范围：仅影响支付回调处理

测试情况：
- 本地复现成功
- 修复后测试通过"

git push origin hotfix/order-payment-status-bug

# 创建紧急 PR，通知孙八（测试）立即审查
```

```bash
# 孙八（测试）：紧急审查和测试
# 1. 代码审查
# 2. 编写回归测试用例
# 3. 测试环境验证
# 4. 上线前确认

# 审查通过后
git add .
git commit -m "test: 添加支付状态更新回归测试"
git push origin hotfix/order-payment-status-bug
```

```bash
# 李四：合并 hotfix
git checkout main
git pull origin main
git merge origin/hotfix/order-payment-status-bug

# 打补丁标签
git tag -a v1.0.1 -m "补丁版本 1.0.1

修复内容：
- 修复支付状态更新失败问题

紧急程度：高
影响范围：支付回调处理"

git push origin main
git push origin v1.0.1

# 合并回 develop
git checkout develop
git merge main
git push origin develop

# 清理分支
git branch -d hotfix/order-payment-status-bug
git push origin --delete hotfix/order-payment-status-bug
```

### 4.6 完整的团队协作流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Sprint 开发周期                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Day 1                    Day 3-5                   Day 7                    │
│    │                         │                        │                       │
│    ▼                         ▼                        ▼                       │
│ ┌──────┐    每个人        ┌──────┐    代码审查       ┌──────┐   功能集成      │
│ │Sprint│ ──────────────► │开发中│ ────────────────► │准备发│ ───────────────► │
│ │启动  │   创建功能分支   │      │   PR + 合并      │布    │   合并到 main   │
│ └──────┘                 └──────┘                   └──────┘                  │
│                              │                                                │
│                              │ 发现 Bug                                       │
│                              ▼                                                │
│                        ┌──────────┐                                           │
│                        │本地自测  │                                           │
│                        └──────────┘                                           │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                              发布后维护                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  用户反馈 ──► 发现 Bug ──► 创建 hotfix ──► 紧急审查 ──► 合并发布 ──► 结束    │
│                                     │                                        │
│                                     │                                        │
│                              ┌────────────┐                                   │
│                              │   测试验证  │                                   │
│                              └────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 常见问题与解决方案

### 5.1 场景化问题处理

```bash
# ============================================
# Q1: 不小心把大文件提交了，怎么从历史记录中删除？
# ============================================

# 1. 先从所有提交中删除这个文件
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatched big-file.zip" \
  --prune-empty --tag-name-filter cat -- --all

# 2. 使用更现代的工具 BFG Repo-Cleaner
# 下载 bfg.jar
java -jar bfg.jar --delete-files big-file.zip

# 3. 清理并推送
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push --force --all

# ============================================
# Q2: 提交信息写错了，怎么修改？
# ============================================

# 还没 push
git commit --amend
# 会打开编辑器，可以修改提交信息

# 已经 push（需要谨慎）
git commit --amend
git push --force origin branch-name


# ============================================
# Q3: 不小心在 main 分支上开发了，怎么移到新分支？
# ============================================

# 方法 1：创建新分支，保留 main 的修改
git branch feature/temp-work
git reset --hard origin/main
git checkout feature/temp-work

# 方法 2：如果还没 commit
git stash
git checkout -b feature/new-branch
git stash pop


# ============================================
# Q4: 怎么撤销某个特定文件的修改？
# ============================================

# 恢复到最新提交状态
git checkout -- filename.txt

# 恢复到某个特定提交的状态
git checkout commit-id -- filename.txt


# ============================================
# Q5: 怎么查看某个文件在某个版本的内容？
# ============================================

# 查看某个提交时的文件内容
git show commit-id:filename.txt

# 比较两个提交中文件的差异
git diff commit1 commit2 -- filename.txt


# ============================================
# Q6: 远程分支被删除了，本地还显示，怎么清理？
# ============================================

git fetch --prune
# 或者
git remote prune origin


# ============================================
# Q7: 怎么给历史提交打标签？
# ============================================

git tag -a v1.0.0 commit-id -m "为特定提交打标签"
git push origin v1.0.0


# ============================================
# Q8: .gitignore 规则不生效，已经提交的文件怎么处理？
# ============================================

# 1. 确认 .gitignore 规则正确
# 2. 从暂存区移除文件
git rm --cached filename
git rm -r --cached folder/

# 3. 提交这个改变
git commit -m "chore: 从版本控制移除不需要的文件"

# 4. 以后这个文件就会被忽略
```

### 5.2 Git 配置别名（提升效率）

```bash
# 创建快捷命令
git config --global alias.st status
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.ci commit
git config --global alias.df diff
git config --global alias.lg "log --oneline --graph --all"

# 高级别名
git config --global alias.last "log -1 HEAD"
git config --global alias.unstage "reset HEAD --"
git config --global alias.visual "!gitk"
```

---

## 6. Git 钩子与自动化

### 6.1 Git 钩子简介

```
Git 钩子触发时机：

  准备提交    ┌─────────────────────────────────┐
    ───────► │          pre-commit              │
              │  （提交前执行，可阻止提交）        │
              └─────────────────────────────────┘
                            │
                            │ 通过
                            ▼
              ┌─────────────────────────────────┐
              │         commit-msg               │
              │  （验证提交信息格式）              │
              └─────────────────────────────────┘
                            │
                            │ 通过
                            ▼
                       提交成功！

  ┌─────────────────────────────────┐
  │         post-commit             │
  │  （提交后执行，触发 CI/CD）      │
  └─────────────────────────────────┘

  合并操作    ┌─────────────────────────────────┐
    ───────► │          pre-push                │
              │  （推送前执行，可阻止推送）       │
              └─────────────────────────────────┘
```

### 6.2 实用钩子示例

#### pre-commit：检查代码格式

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "执行代码格式检查..."

# 检查 Java 文件格式
if git diff --cached --name-only | grep '\.java$'; then
    # 检查是否使用了 Google Java Format
    if ! command -v google-java-format &> /dev/null; then
        echo "警告: google-java-format 未安装，跳过格式检查"
        exit 0
    fi
    
    # 获取暂存的 Java 文件
    FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.java$')
    
    for file in $FILES; do
        if ! google-java-format -i "$file" 2>/dev/null; then
            echo "代码格式检查失败: $file"
            exit 1
        fi
    done
    
    # 重新添加格式化后的文件
    git add $FILES
fi

# 检查是否包含敏感信息
if grep -r "password\s*=" --include='*.properties' --include='*.yml' --include='*.yaml' . 2>/dev/null | grep -v "password.*=" | grep -v "^#"; then
    echo "错误: 检测到可能包含密码的配置文件"
    echo "请确保敏感信息使用环境变量或配置文件模板"
    exit 1
fi

echo "代码格式检查通过！"
exit 0
```

#### commit-msg：验证提交信息格式

```bash
#!/bin/bash
# .git/hooks/commit-msg

COMMIT_MSG=$(cat "$1")
COMMIT_PATTERN="^(feat|fix|docs|style|refactor|test|chore|hotfix)(\(.+\))?: .{1,50}"

if ! echo "$COMMIT_MSG" | grep -E "$COMMIT_PATTERN" > /dev/null; then
    echo ""
    echo "=============================================="
    echo "提交信息格式错误！"
    echo ""
    echo "正确格式：type(scope): subject"
    echo ""
    echo "type 可选值："
    echo "  feat     - 新功能"
    echo "  fix      - Bug 修复"
    echo "  docs     - 文档更新"
    echo "  style    - 代码格式（不影响功能）"
    echo "  refactor - 重构（不是新功能或修复）"
    echo "  test     - 测试相关"
    echo "  chore    - 构建/工具相关"
    echo "  hotfix   - 紧急修复"
    echo ""
    echo "示例："
    echo "  feat(order): 添加订单导出功能"
    echo "  fix: 修复支付回调异常"
    echo "=============================================="
    exit 1
fi

exit 0
```

### 6.3 CI/CD 集成示例（GitHub Actions）

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  push:
    branches: [main, develop, 'release/**', 'hotfix/**']
  pull_request:
    branches: [main, develop]

jobs:
  # ============================================
  # 作业 1：代码质量检查
  # ============================================
  lint:
    name: Code Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        
      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
          
      - name: Cache Maven packages
        uses: actions/cache@v3
        with:
          path: ~/.m2/repository
          key: ${{ runner.os }}-maven-${{ hashFiles('**/pom.xml') }}
          
      - name: Run Checkstyle
        run: mvn checkstyle:check
        
      - name: Run SpotBugs
        run: mvn spotbugs:check

  # ============================================
  # 作业 2：单元测试
  # ============================================
  test:
    name: Unit Tests
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
        
      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
          
      - name: Run Tests
        run: mvn test
        
      - name: Generate Coverage Report
        run: mvn jacoco:report
        
      - name: Upload Coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./target/site/jacoco/jacoco.xml

  # ============================================
  # 作业 3：安全扫描
  # ============================================
  security:
    name: Security Scan
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
        
      - name: Run OWASP Dependency Check
        run: mvn org.owasp:dependency-check-maven:check
        
      - name: Upload Security Report
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: security-report
          path: target/dependency-check-report.html

  # ============================================
  # 作业 4：构建与部署
  # ============================================
  build:
    name: Build & Deploy
    runs-on: ubuntu-latest
    needs: security
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
        
      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
          
      - name: Build with Maven
        run: mvn clean package -DskipTests
        
      - name: Deploy to Staging
        run: |
          echo "部署到预发环境..."
          # 实际部署命令
          
      - name: Run Integration Tests
        run: |
          echo "运行集成测试..."
          # 集成测试命令
```

---

## 7. 安全与权限管理

### 7.1 GitHub 仓库权限设置

```
仓库权限层级：

Owner（所有者）
  ├─ 完全控制权限
  ├─ 可管理成员权限
  ├─ 可删除仓库
  └─ 可转让仓库

Admin（管理员）
  ├─ 管理仓库设置
  ├─ 管理分支保护
  └─ 管理拉取请求

Maintain（维护者）
  ├─ 管理非分支设置
  ├─ 管理标签
  └─ 管理项目

Write（开发者）
  ├─ 推送代码
  ├─ 管理分支
  └─ 创建 PR

Triage（分类者）
  ├─ 管理 Issues
  └─ 管理 PR

Read（阅读者）
  └─ 只读访问
```

### 7.2 分支保护规则

```bash
# ============================================
# 在 GitHub 中设置分支保护规则
# ============================================

# 推荐的保护规则配置：

# 1. 基本保护
require pull request before merging    ✓  要求 PR 才能合并
require reviews before merging        ✓  至少 1 人审查
dismiss stale reviews                 ✓  新提交自动解除审查
require status checks to pass         ✓  必须通过 CI 检查

# 2. 强保护（对于 main 分支）
require 2+ reviews before merging     ✓  至少 2 人审查
include administrators                ✓  管理员也需审查
require conversation resolution        ✓  必须解决所有评论
require linear history                ✓  要求线性历史

# 3. 强制推送限制
allow force pushes                    ✗  禁止强制推送
allow deletions                       ✗  禁止删除分支
```

### 7.3 企业安全最佳实践

```bash
# ============================================
# 1. 保护敏感信息
# ============================================

# .gitignore 模板
cat > .gitignore << 'EOF'
# IDE
.idea/
.vscode/
*.iml

# Java
target/
*.class
*.jar
*.war

# 敏感文件
*.properties
*.env
credentials.json
secrets.yaml

# 日志
*.log
logs/

# 临时文件
*.tmp
*.swp
EOF

# ============================================
# 2. 使用 GitHub Secrets 管理密钥
# ============================================

# 在 GitHub 仓库 Settings > Secrets 中添加：
# DATABASE_PASSWORD=xxxxx
# API_KEY=xxxxx
# DEPLOY_TOKEN=xxxxx

# 在 Actions 中使用
- name: Deploy
  env:
    DATABASE_PASSWORD: ${{ secrets.DATABASE_PASSWORD }}

# ============================================
# 3. CODEOWNERS 文件定义代码负责人
# ============================================

# 创建 CODEOWNERS 文件
cat > CODEOWNERS << 'EOF'
# 默认负责人
* @company/dev-team

# 各模块负责人
/src/orders/ @zhangsan @lisi
/src/payment/ @wangwu @zhaoliu
/src/user/ @qianqi

# 基础设施
/.github/ @devops-team
/infra/ @devops-team

# 文档
*.md @tech-writer
EOF
```

---

## 附录：Git 命令速查卡

```
┌────────────────────────────────────────────────────────────────────┐
│                        日常工作流                                   │
├────────────────────────────────────────────────────────────────────┤
│  开始工作：git checkout main && git pull                           │
│  创建分支：git checkout -b feature/xxx                              │
│  提交代码：git add . && git commit -m "msg"                         │
│  推送代码：git push -u origin feature/xxx                          │
├────────────────────────────────────────────────────────────────────┤
│                        分支操作                                     │
├────────────────────────────────────────────────────────────────────┤
│  查看分支：git branch / git branch -a                               │
│  切换分支：git checkout xxx / git switch xxx                        │
│  创建分支：git branch xxx                                           │
│  删除分支：git branch -d xxx                                        │
│  合并分支：git merge xxx                                            │
├────────────────────────────────────────────────────────────────────┤
│                        查看历史                                      │
├────────────────────────────────────────────────────────────────────┤
│  查看状态：git status                                               │
│  查看差异：git diff / git diff --staged                            │
│  查看日志：git log / git log --oneline --graph                     │
│  查看提交：git show xxx                                             │
├────────────────────────────────────────────────────────────────────┤
│                        撤销操作                                      │
├────────────────────────────────────────────────────────────────────┤
│  丢弃修改：git restore xxx / git checkout -- xxx                    │
│  取消暂存：git restore --staged xxx / git reset HEAD xxx            │
│  回退提交：git reset --soft/mixed/hard HEAD~n                       │
│  反向提交：git revert xxx                                           │
├────────────────────────────────────────────────────────────────────┤
│                        远程操作                                      │
├────────────────────────────────────────────────────────────────────┤
│  克隆仓库：git clone url                                            │
│  拉取代码：git fetch / git pull                                    │
│  推送代码：git push                                                 │
│  查看远程：git remote -v                                            │
└────────────────────────────────────────────────────────────────────┘
```

---

## 总结

企业使用 Git 的核心要点：

1. **选择合适的分支策略**：根据团队规模和发布周期选择 Git Flow、GitHub Flow 或 Trunk-Based

2. **养成良好的提交习惯**：频繁提交、使用有意义的提交信息、保持提交原子性

3. **重视代码审查**：所有代码都需要经过审查才能合并，这是质量保障的重要环节

4. **正确处理冲突**：优先在功能分支解决冲突，避免在 main 分支直接修改

5. **谨慎操作历史**：尽量使用 `git revert` 而不是 `git reset`，避免强制推送

6. **保护敏感信息**：永远不要将密钥、密码等敏感信息提交到版本库

7. **自动化流程**：利用 Git 钩子和 CI/CD 减少人工错误，提高效率

掌握以上内容，你就能在企业中游刃有余地使用 Git 进行团队协作开发了！
