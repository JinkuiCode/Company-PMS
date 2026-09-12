# 金蝶官方 Python SDK

- 文件：`k3cloud_webapi_sdk-3.0.0-py3-none-any.whl`
- 来源：[金蝶官方 SDK 介绍](https://open.kingdee.com/K3Cloud/Open/ApiCenterReportDetail.aspx) 中的 OpenAPI 资料包。
- 下载：[金蝶云星空新版 WebAPI 资料包](https://file.open.kingdee.com/WebAPI/%E9%87%91%E8%9D%B6%E4%BA%91%E6%98%9F%E7%A9%BA_%E6%96%B0%E7%89%88WebAPI%E8%B5%84%E6%96%99%E5%8C%85.rar)。取其 Python 目录中的原始 wheel，未修改文件。
- 取得日期：2026-09-10。该资料包中 Python 示例标记 2021-08-31；3.0.0 是本次固定验证版本，不声称为最新版本。
- SHA-256：`b8e40f96ac143028dbb5fb732ec7e6c513628603070aabf3e53678a34e308056`
- wheel 元数据声明 MIT License，依赖 requests / urllib3。

PMS 使用 `K3CloudApiSdk.InitConfig()` 与 `BuildHeader()` 生成官方签名，传输仍由现有 httpx 客户端负责，避免改变现有保存响应三态、超时及重试语义。每个客户端持有自身配置，不共享跨账号的 SDK 会话。

在 backend 目录运行 `python -m pip install -r requirements.txt`。不使用不明来源重打包 SDK，也不将应用凭据写入此目录。
