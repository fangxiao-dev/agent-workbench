# 私有页面的数据边界

当一个页面既有稳定的 UI 外壳，又要读取 Customer、Supplier Operator 或其他按请求确定的私有数据时，把私有读取放进独立的 async content，并以 Suspense 包住该 content。外壳、标题和 loading state 可以先渲染；数据区在访问主体确认后再读取。

这是一种推荐模式，不是全局硬规则。外层若读取 cookies、session 或权限，页面仍是 request-time dynamic；“稳定 shell”不等于静态生成。

## 采用条件

- 页面有可先显示的外壳，私有数据区可以独立 loading。
- 访问主体必须先解析，才能安全查询其订单、配置、文件或其他私有数据。
- 独立 data content 能形成有价值的测试 seam，例如验证 access → data-read 的顺序或未授权时不读取主体数据。

## 结构

```tsx
export default function HistoryPage() {
  return <Suspense fallback={<HistorySkeleton />}><HistoryContent /></Suspense>
}

export async function HistoryContent() {
  const customer = await getCurrentCustomer()
  const orders = await getOrderHistory(customer.id)
  return <OrderHistoryList orders={orders} />
}
```

- data content 只接受已经确认的主体 identity；不得用 URL、表单或浏览器传来的 Customer ID 直接查询私有数据。
- 只有当导出 content 能让测试直接验证边界或调用顺序时才 export；不要为“可测试”而拆出无意义的 wrapper。
- 按 UI 的真实 loading、empty、unauthorized 和 error state 设计 fallback 与边界；Suspense 不能替代鉴权或错误处理。

## 不采用的情况

- 纯静态页面，或没有私有/个性化读取的页面。
- 页面太小，拆分不会形成独立 loading 或测试边界。
- 多项读取必须以同一原子快照呈现，拆分会造成可见的不一致；先设计一致性边界。
- 主要交互和数据生命周期已在 Client Component 中受控；此时评估 client-side state 与 loading contract，而不是强套 server async content。

## 检查点

- 不把“Suspense shell”误称为静态渲染。
- 测试 access/identity 先于 repository 或 service data read；拒绝访问时不泄露或复用私有结果。
- 页面外壳不暴露 record ID、integration ID 或其他仅供诊断的字段；遵守 `ui-commonsense` 的 User-Facing Data Rule。
