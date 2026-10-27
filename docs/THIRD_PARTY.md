# 依赖与素材说明

- Python 运行时：Python Software Foundation License，https://docs.python.org/3/license.html 。
- PySide6 / Qt：采用随依赖提供的开源许可条款，https://doc.qt.io/qtforpython-6/licenses.html 。分发物应保留 Qt、PySide、Shiboken 和所用 Qt 组件的许可及必要声明，使用动态库形式；正式公开分发前复核该版本实际包含的组件。
- LGPL/GPL 与 Python 许可文本保存在 `vocabulary_app/resources/licenses` 并随应用包分发。Qt 6.12 与 PySide6 6.12.0 的对应源代码可从 https://download.qt.io/official_releases/qt/ 和 https://download.qt.io/official_releases/QtForPython/pyside6/ 获取。应用包保留动态库文件，允许按许可替换兼容库。
- PyInstaller 构建工具：GPL 加应用分发例外，https://pyinstaller.org/en/stable/license.html 。
- 发音使用 Windows 已安装的 SAPI 语音；不打包或重新分发系统语音资源。缺少相应口音时显示缺失状态。
- 原 180 个基础词条与新增 ECDICT 精选词条分别记录来源。ECDICT 固定版本 `ab22ad36302cafc6349a050e2b60894855208055` 使用上游 MIT 许可，完整许可保存在 `resources/licenses/ECDICT-MIT.txt`；实际范围与固定源文件哈希见 CONTENT.md。项目代码许可与原基础内容许可分别决定，不把所有资源统一标为 MIT。
- 界面以白底、蓝粉强调和留白作为设计方向，使用基础控件和程序绘制图形，不复制第三方品牌标志、账号、宣传图或角色素材。

开发参考：Qt for Python 官方安装与 API 文档，PyInstaller 官方构建与运行时文档。开发工具和依赖不要求购买付费服务；程序没有广告、支付或订阅。
