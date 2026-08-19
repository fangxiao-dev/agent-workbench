# Safety Review 五类审查清单

safety-review 完整审查时按以下五类逐项审查实现与测试证据；收缩型 focused path 不加载本清单。本文件由 leaf 按需加载。

## 1. Data integrity

检查数据写入、schema/data migration、事务边界、校验、重试与 rollback。报告可能重复写、部分写、丢失、损坏或无法恢复的路径，以及证据是否覆盖失败恢复。

## 2. Security boundary

检查认证、authorization/permission、tenant 或数据隔离、secret 处理、输入信任边界和 webhook 签名验证。重点是调用是否能绕过应有的 auth 或 permission 检查。

## 3. Concurrency

检查竞态、重复投递、at-least-once handler、锁/版本控制、幂等键和重试交互。不要因"目前串行执行"而忽略外部回调、队列或用户并发。

## 4. External side effects

检查 payment、webhook、邮件、供应商 API、数据库外写入和其他 external mutation。每项写入应有可核实的 idempotency、去重或 compensation/rollback 语义；报告其失败和重试路径。

## 5. Change map

列出受影响的入口、写入点、数据存储、外部 adapter、异步消费者、迁移及验证证据，并标出未审计或无法确认的路径。change map 是本次报告的一部分，不是新 artifact。
