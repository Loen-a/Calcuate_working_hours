# 踩坑记录/

实际遇到过的 bug。**写"为什么会发生"比"怎么修"更重要**——以后遇到类似情况能快速对号入座。

## 什么时候记

- 非 trivial 的 bug（runtime ReferenceError、缺 import、类型不严、逻辑错）
- 跟工具 / 框架 / 浏览器特性相关（bundler、TypeScript、file:// 行为）
- 调试过程有启发性的

## 一条记录写什么

- **现象**（错误信息 / 用户报告）
- **Root cause**（为什么发生）
- **修复**
- **怎么避免**（规则 / 工具 / checklist）
