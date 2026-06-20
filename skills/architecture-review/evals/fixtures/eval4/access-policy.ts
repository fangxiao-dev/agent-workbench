export type TemporaryGrant = {
  documentId: string;
  granteeUserId: string;
  expiresAt: Date;
  revokedAt: Date | null;
};

export type DocumentRecord = {
  id: string;
  ownerUserId: string;
};

export function canReadDocument(
  userId: string,
  document: DocumentRecord,
  grants: TemporaryGrant[],
  now: Date,
) {
  if (document.ownerUserId === userId) {
    return true;
  }

  return grants.some((grant) => {
    return (
      grant.documentId === document.id &&
      grant.granteeUserId === userId &&
      grant.revokedAt === null &&
      grant.expiresAt > now
    );
  });
}
