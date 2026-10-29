# Impl-Package 交接

适用于当前工作由 Impl-Package harness 管理的开发续接。交接负责定位和补充；状态恢复与裁决由 owning workflow 负责。

## 恢复入口

给出 package 路径、实际工作区和当前 owning workflow。开发续接指向 `/impl-package:dev-with-track` 的 Restore，让接手者从当前可用的 Skill 定位 harness，catch up 后继续。执行协作沿用 `$dispatcher`，不在交接中复制调度或审查流程。

不复制 Ticket 状态、Gate、完整待办或测试矩阵；这些由 harness 重新读取。主控判断 harness 已覆盖的前因后果、关键决定、成果、开放问题和下一步均可省略。只有会影响恢复的未登记事实需要补充，例如未提交改动的归属、在途操作、尚未落盘的决定或已知恢复障碍。

## 必要的现场提示

- 工作区、branch／HEAD、dirty状态只在影响定位、差异判断或保护现有工作时带上；它们是交接时快照，不替代接手时的实际检查。
- 发现HEAD变化或dirty路径时先识别相关diff与归属；不凭不一致直接认定无法接手，不重置或覆盖现有工作。
- 入口或harness不可用时说明缺口，回到owning workflow恢复；不创建另一套状态协议，不把旧Gate当本次验收。

恢复后的首个动作可以是“按当前包状态继续执行”，无需另抄next-action清单。harness不能恢复的用户约束与未沉淀经验由主干章节承接。
