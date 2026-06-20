import { completeJob, leaseNextJob, submitJob } from "./job-runner";
import { db } from "./infra";

async function expectOutboxRows(params: {
  topic: string;
  targetId: string;
  count: number;
}) {
  const rows = await db.outbox.findMany({
    where: { topic: params.topic, targetId: params.targetId },
  });
  expect(rows).toHaveLength(params.count);
}

async function expectAuditRow(params: {
  actor: string;
  action: string;
  targetId: string;
}) {
  const row = await db.auditLog.findFirst({
    where: {
      actor: params.actor,
      action: params.action,
      targetId: params.targetId,
    },
  });
  expect(row).not.toBeNull();
}

test("returns the existing job for a duplicate idempotency key", async () => {
  const first = await submitJob({
    type: "sync",
    payload: { account: "ops" },
    idempotencyKey: "idem_1",
    actor: "ops-user",
  });

  const second = await submitJob({
    type: "sync",
    payload: { account: "ops" },
    idempotencyKey: "idem_1",
    actor: "ops-user",
  });

  expect(second.id).toBe(first.id);
});

test("creates one durable outbox dispatch row for duplicate submits", async () => {
  const first = await submitJob({
    type: "sync",
    payload: { account: "ops" },
    idempotencyKey: "idem_1b",
    actor: "ops-user",
  });

  await submitJob({
    type: "sync",
    payload: { account: "ops" },
    idempotencyKey: "idem_1b",
    actor: "ops-user",
  });

  await expectOutboxRows({
    topic: "job.pending",
    targetId: first.id,
    count: 1,
  });
});

test("only one worker can lease the pending job", async () => {
  await submitJob({
    type: "sync",
    payload: { account: "ops" },
    idempotencyKey: "idem_2",
    actor: "ops-user",
  });

  const [workerA, workerB] = await Promise.all([
    leaseNextJob("worker-a"),
    leaseNextJob("worker-b"),
  ]);

  expect([workerA, workerB].filter(Boolean)).toHaveLength(1);
});

test("completion is audited and requires the leasing worker", async () => {
  const job = await submitJob({
    type: "sync",
    payload: { account: "ops" },
    idempotencyKey: "idem_3",
    actor: "ops-user",
  });

  const leased = await leaseNextJob("worker-a");
  expect(leased?.id).toBe(job.id);

  await expect(completeJob({
    jobId: job.id,
    workerId: "worker-b",
    result: { ok: true },
  })).rejects.toThrow("job-not-leased-by-worker");

  await completeJob({
    jobId: job.id,
    workerId: "worker-a",
    result: { ok: true },
  });

  await expectAuditRow({
    actor: "worker-a",
    action: "job.completed",
    targetId: job.id,
  });
});
