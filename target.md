# 项目背景
1.目前使用codex+cc switch接入kimi的模型时遇到问题，官方提供的kimi code的接口，与openai的标准协议不兼容
2.从结果看，只能兼容kimi通用模型的url https://api.moonshot.cn/v1，不兼容 kimi code的url https://api.kimi.com/coding/v1
3.根据结果反馈，不兼容原因有以下几点：
- 端点白名单：api.kimi.com/coding/v1 是 Kimi Code 专用编程接口，目前仅面向 Claude Code、Roo Code、Kilo Code、Kimi CLI 等特定 Coding Agent 开放。Codex 作为 OpenAI 官方工具，请求会被服务端拒绝或返回 404。
- 协议不匹配：新版 Codex 默认使用 wire_api = "responses"（OpenAI Responses API），而 Kimi Code 端点主要兼容 Chat Completions，对 Responses API 的路径（如 /responses）支持不完整，导致路径找不到。
- CC Switch 只是代理：CC Switch 负责把 Codex 的流量转发到你填写的地址，但如果目标端点本身就不支持 Codex 的请求格式，代理层无法解决 404。


# 项目目标

- [] 根据当前的项目背景生成windows下的应用解决上面问题
- [] 本地启动一个代理，把 Codex 的 Responses API 翻译成标准 Chat Completions，再转发到 Kimi Code 
- [] 配置后 Codex 实际连接的是本地中转地址( 例如http://localhost:8317/v1)
- [] 不限制代码语言，当然尽量使用python或者c/c++
- [] 项目添加git信息
- [] 应用界面参考cc switch软件界面设计，功能要可配置，后续可能要兼容其也有相同情况，无法接入codex的模型