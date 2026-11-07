# Goal, Value And Convergence

These rules apply to every mode and to every loop over a mode.

1. **Goal and boundary first.** Before the first round the controller writes a short 目标与边界 block at the top of the `--topic` text: what this discussion must decide or produce, and which questions belong to other stages. It stays fixed for the whole run unless the user changes the goal.
2. **Value is measured against the goal.** An item has value when adopting it would change a decision, the contract, a safety boundary or feasibility within the current goal. A correct point that belongs to another stage is recorded and handed to that stage.
3. **Two judgments.** Participants filter what they raise by the goal block. The controller then classifies every returned item against the same block, with a one-sentence reason: valuable, handed over (with the owning stage), needs evidence (with the evidence that would decide it), or duplicate.
4. **Convergence.** A round converges when, after the controller's classification, it holds no new valuable item; when the user names the target high risk, two consecutive such rounds are required. Valuable items are fixed in the target before the next round. Items that need evidence do not extend the loop. At the round ceiling, remaining valuable items go to the user as decisions.
5. **Report.** Each round lists its items by class; the final report states why the run stopped.
