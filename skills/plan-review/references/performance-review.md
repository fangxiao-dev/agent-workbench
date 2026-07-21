# Performance Review

检查数据库 N+1、API/工具调用放大、内存增长、缓存一致性与失效、同步 IO、慢路径、算法复杂度、批量规模和容量假设。

把性能风险连接到实际 workload、用户影响或资源上限。没有相关行为或证据时记录 `not_applicable` 及理由，不生成“未来可优化”式 finding。

对调用放大说明输入规模与 query/API/tool 次数的关系；检查 queue、worker/concurrency pool、connection pool、backpressure、timeout budget 和资源释放。结论依赖吞吐或延迟时，要求 benchmark、profiling、production metric 或有界规模估算作为验证 oracle，不以“看起来慢”晋升 finding。

当性能与正确性相互影响时优先指出正确性风险，例如缓存陈旧、超时后的重复执行或内存压力导致的部分失败。
