# S02 图标重叠修复

2026-10-13（香港时间）。用户截图显示折叠箭头与上传图标的名称以普通文字显示，覆盖标签。

根因：`app/views/data_center.py` 的字体选择器 `html,body,[class*="st-"]` 匹配 Streamlit 图标节点，覆盖 `Material Symbols Rounded` 字体。实际 Chrome 中图标文件已加载，但计算字体为 PingFang／system-ui；首个浏览器回归检查失败，复现用户问题。

修复：只保留 `html,body` 的基础字体样式，保留图标节点自己的字体，不增加尺寸／间距补丁。原运行服务仍缓存旧模块，已重启本机 127.0.0.1:8501 服务以加载修复。

验证：Chrome 浏览器回归先失败、修复后通过；箭头和上传图标计算字体全部为 Material Symbols Rounded，字体已加载；两个折叠区均可展开，展开后字体仍正确。实际检查了 1440 像素宽度的折叠截图与 720 像素宽度的展开截图，所报告的图标文字重叠消失。没有进行原生文件选择／下载验证。

界面回归命令：`.venv/bin/python -m pytest tests/test_data_center.py -q`，退出 0，13 passed in 3.30s。仅改动界面字体作用范围；导入核心未变。

证据：ui_icons_red_checks.json、ui_icons_green_checks.json、ui_icons_red.png、ui_icons_green.png、ui_icons_green_expanded_720.png。一次性浏览器检查代码保存为 ui_icons_check.mjs；使用系统 Node 与独立临时 Chrome 调试端口 9223，不增加项目依赖，不使用个人浏览器配置。

服务器保持运行。用户刷新页面即可加载修复；需要绕过浏览器缓存时，可用 Cmd+Shift+R。
