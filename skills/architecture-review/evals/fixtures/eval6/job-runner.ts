import { db } from "./infra";

export async function submitJob(input: {
  type: string;
  payload: unknown;
  idempotencyKey: string;
  actor: string;
}) {
  return db.$transaction(async (tx) => {
    const created = await tx.job.upsert({
      where: { idempotencyKey: input.idempotencyKey },
      create: {
        type: input.type,
        payload: input.payload,
        idempotencyKey: input.idempotencyKey,
        status: "pending",
      },
      update: {},
    });

    await tx.auditLog.create({
      data: {
        actor: input.actor,
        action: "job.submitted",
        targetId: created.id,
      },
    });

    await tx.outbox.create({
      data: {
        topic: "job.pending",
        targetId: created.id,
        idempotencyKey: `dispatch:${created.id}`,
      },
      skipDuplicates: true,
    });

    return created;
  });
}

export async function leaseNextJob(workerId: string) {
  return db.$transaction(async (tx) => {
    const job = await tx.job.findFirst({
      where: { status: "pending" },
      orderBy: { createdAt: "asc" },
    });
    if (!job) {
      return null;
    }

    const claimed = await tx.job.updateMany({
      where: { id: job.id, status: "pending" },
      data: { status: "leased", leasedBy: workerId },
    });
    if (claimed.count !== 1) {
      return null;
    }

    await tx.auditLog.create({
      data: {
        actor: workerId,
        action: "job.leased",
        targetId: job.id,
      },
    });

    return tx.job.findUniqueOrThrow({ where: { id: job.id } });
  });
}

export async function completeJob(input: {
  jobId: string;
  workerId: string;
  result: unknown;
}) {
  return db.$transaction(async (tx) => {
    const updated = await tx.job.updateMany({
      where: {
        id: input.jobId,
        status: "leased",
        leasedBy: input.workerId,
      },
      data: {
        status: "completed",
        result: input.result,
      },
    });

    if (updated.count !== 1) {
      throw new Error("job-not-leased-by-worker");
    }

    await tx.auditLog.create({
      data: {
        actor: input.workerId,
        action: "job.completed",
        targetId: input.jobId,
      },
    });

    return tx.job.findUniqueOrThrow({ where: { id: input.jobId } });
  });
}
