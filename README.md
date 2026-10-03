# SailCloth-01 · 帆布浸渍防水台

帆布间布卷与浸渍固化台账基线项目（Django 5 + DRF + Vue 3 SPA）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Django 5 · DRF · SimpleJWT · django-cors-headers · Gunicorn |
| 前端 | Vue 3 · Vite · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 |
| 部署 | Docker Compose · Nginx（前端反代 `/api`） |

## 路径与端口

- **项目路径**：`d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01`
- **前端**：http://localhost:3740
- **API**：http://localhost:8740
- **PostgreSQL**：localhost:6140

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。后端 entrypoint 执行 migrate + seed。

## 业务规则

1. 布卷状态从「原布」(`raw`) 改为「浸渍中」(`dipping`) 前，该卷必须持有一张**未归还的绷架占用牌** (`StretcherTag`)；无牌时后端以中文拦截。
2. 布卷状态不可设为「已固化」（`cured`），除非该卷**最近一条** `DipRun` 的 `cureHours` 已记录且 **≥ 12**。固化判断不掺占架规则（有无牌、牌是否归还都不影响固化）。

绷架占用牌规则：

- 字段：布卷、绷架号（1–99 整数）、占出时刻、归还时刻（可空）、占架人。
- 同一绷架号在未归还期间不得被第二卷占用；同一卷未归还牌至多一张（数据库部分唯一索引兜底，并发抢架只放行一卷，负方得 409 中文提示）。
- 操作工可占架与归还；已固化卷禁止新占。

规则实现：`backend/core/rules.py`

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## SPA 信息架构

- **登录** → 进入主工作面
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`，占用中的卷芯片显示绷架号）；点击打开右侧面板登记 `DipRun`、切换固化状态；原布无未归还牌时「标为浸渍中」被中文挡住，面板可直达绷架占用
- **`/stretchers` · 绷架占用**：未归还占用牌列表（绷架号/布卷/占架人/占出时刻）、占出（选卷+架号 1–99）、归还，附 1–99 架面占用图
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD，侧栏降级为「台账」入口，非主路径

API：`/api/lofts|rolls|dips|stretcher-tags|dashboard/`（占出 `POST stretcher-tags/`，归还 `POST stretcher-tags/{id}/return_tag/`，未归还筛 `?open=1`）。

种子：一原布、零占用牌。

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
