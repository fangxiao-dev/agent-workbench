import { db } from "./db";

export async function changeMemberRole(params: {
  actorUserId: string;
  targetUserId: string;
  nextRole: "admin" | "member";
  reason: string;
}) {
  const actor = await db.user.findUniqueOrThrow({
    where: { id: params.actorUserId },
    include: { permissions: true },
  });

  if (!actor.permissions.includes("members.manage")) {
    throw new Error("forbidden");
  }

  const previous = await db.user.findUniqueOrThrow({
    where: { id: params.targetUserId },
  });

  await db.user.update({
    where: { id: params.targetUserId },
    data: { role: params.nextRole },
  });

  return {
    targetUserId: params.targetUserId,
    previousRole: previous.role,
    nextRole: params.nextRole,
  };
}
