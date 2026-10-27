# vocabulary-learning-website

Windows 单词学习软件。提供离线 20 词学习、首次自评/测评引导、错词重学重测、错题本、历史、目标、基础成就和本地备份。项目名沿用仓库名称，当前交付为桌面应用。

主页是各模块的入口。进入学习等模块后，界面只保留该模块内容与“返回主页”；目标进度条常驻主页底部。

首次启动先选当前水平，可以按自评快速开始，也可以选 20、50、100、200、500 题进行词义测评，然后设置目标。测评每题保存，退出后可接着做；结果只作为推荐难度和估计区间，不代表所有语言技能。已有档案不会被强制重做引导，重新测评后可明确采用推荐难度，原目标和记录保留。

## 直接运行

构建后双击 `dist\VocabularyLearning\VocabularyLearning.exe`，或双击根目录 `run.cmd`。应用包包含 Python 与 Qt 运行时；请保留整个 `VocabularyLearning` 文件夹。

学习记录存放在 `%LOCALAPPDATA%\VocabularyLearning`。更新程序时保留这个目录；建议在设置中定期导出记录。首版不需要账号或网络。

## 开发运行

采用 Python 3.12、PySide6 6.12.0、SQLite。Python 3.12—3.14 可用，当前构建环境为 Python 3.12.14。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m vocabulary_app
```

PyCharm 打开本目录，解释器选择 `.venv\Scripts\python.exe`，以模块 `vocabulary_app` 运行。可以直接在终端使用上述命令。

```powershell
# 独立演示档案，不混入个人学习记录
.\.venv\Scripts\python.exe -m vocabulary_app --data-dir .\artifacts\demo-profile

# 规则与界面集成验证
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# 在 Windows 构建双击运行的应用文件夹
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

应用文件夹不是安装向导。当前版本未签名。实际已验证的环境、打包状态和限制见 [验证记录](docs/VALIDATION.md)，不把尚未验证的全新 Windows 环境当作已通过。

## 学习规则

- 每轮 20 个不同词。全部最终答对后才结算；中途退出可继续，每次作答均保存。
- 可在总览标记“原本已会”。5 词已会、15 词首次学会，净新增 15；完成后全部 20 词登记掌握。
- 曾错或不会的词最终答对后仍保留在错题本。只剩一个错词也会从原始 20 词池提供四个有效选项。
- 普通词数目标按起点之后的新增部分显示主进度。估计词量与逐词已掌握数量分开。
- 四级按完整指定版本目标词库覆盖率 100% 完成。当前正式四级词表未安装；小型测试词集仅验证规则。
- 成就累计完成新轮次的练习词次；重做历史轮保留记录，不增加唯一词数或练习类成就。

## 修改内容和外观

- 文案：设置 → 编辑界面文案。个人修改保存在学习数据目录的 `ui_texts.json`；默认文案在 `vocabulary_app/resources/ui_texts.json`。
- 配色、字体和间距：`vocabulary_app/resources/theme.json`。
- 词库、等级和成就：`vocabulary_app/resources/content.json`、`levels.json`、`achievements.json`。扩充说明见 [内容说明](docs/CONTENT.md)。
- 资源修改后重新启动，发布包需重新构建；稳定词条 ID 不应因修改显示文字而改变。

当前包含 1080 个独立词元、1274 个义项，L1—L6 各 90 词，L7—L15 各 60 词。L1 从 hi、hello 等基础交流开始，L15 为医学、物理、化学、工程与数学专业术语。分档结合词频、抽象性与专业性，可在配置中调整，尚未标准化校准；不是完整考试词库。新增词条精选自固定版本的 MIT 许可 ECDICT，保留来源与许可。发音只调用 Windows SAPI 本地引擎，可选美音/英音，缺相应本地语音会显示提示。

## 范围与路线图

[产品需求](docs/PRODUCT_REQUIREMENTS.md) · [逐项核对](docs/REQUIREMENTS_CHECKLIST.md) · [实施计划与已确认决定](docs/PLAN.md) · [架构与数据](docs/ARCHITECTURE.md) · [后续路线图](docs/ROADMAP.md) · [依赖与素材](docs/THIRD_PARTY.md)

当前词义测评提供基于版本化内容等级的自适应参考，不是标准化语言能力考试。阅读、写作、真实 3D、阶段奖励、趣味进度和 AI 调用仍按路线图推进。网络策略与 AI 状态独立；当前版本没有模型请求，也不保存 API 密钥。后续公开版使用用户自己的服务商配置。没有公开部署、付费服务或自动同步。
