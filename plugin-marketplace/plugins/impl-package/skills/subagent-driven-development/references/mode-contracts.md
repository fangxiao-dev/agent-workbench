# Mode Contracts

## investigate

```text
Investigation: EVIDENCE_SUFFICIENT | EVIDENCE_GAP
cause: <已证实原因或缺口>
blast radius: <直接影响边界>
existing solution: <可复用方案或 none>
boundary facts: <实施必须保留的事实>
unresolved facts: <none 或最小下一项取证动作>
```

`EVIDENCE_SUFFICIENT` 只释放实施判断，不释放授权、acceptance 或 Gate。investigate 禁止输出 READY|BLOCKED。默认只返回上面 6 行。

## implement

输入只含 source_unit、bounded outcome、ownership、禁改路径、要改的文件列表、一条验证命令和 `strategy`。禁止粘贴整张 Ticket 或全量 AC 到达路径。输出包括变更文件、直接证据、residue/cleanup 和 residual risk；`DONE` 只代表局部单元完成。以 bounded slice 为单位小步派发（见 SKILL「小步切片」），同一 Ticket 不整包交给单个 worker；每 slice 结束后向 progress 文件追加一行进展。

## fix

输入必须包含 finding ID/来源、comparison point、broken invariant、disposition、ownership、禁改范围和验证入口。Fixer 不重新裁决 finding、不扩大范围、不宣称 finding closure；reviewer 必须针对修复后的 comparison point 重新检查。

## review

只执行既定无写副作用的动作，返回 command/procedure、exit status、pass/skip/failure count、首个 actionable failure、cleanup/residue 和必要 artifact pointer。会重写 snapshot、generated file 或工作区内容的命令改走 `implement`/`fix` 或主 session 集成。

## reviewer

Reviewer 使用 `mode=review` 的只读合同，但拥有独立的审查职责。默认只看 caller 列出的路径和 AC ID，不读 plan/spec/contract-design 整章。报告上限：verdict、P0/P1 findings、residual_gaps。`review_scope=checkpoint` 只判断当前 bounded slice 是否满足局部契约；`review_scope=closure` 才判断整个 source unit 是否可以收口。两者都是 fresh invocation；checkpoint PASS 不代表 package 完成，closure PASS 才能支持 closure 判断。Reviewer 发现问题时返回 finding，由 main session 交给 fresh fixer，不在 reviewer invocation 内修复。
