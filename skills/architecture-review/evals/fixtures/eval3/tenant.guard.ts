// Resolves the active organization for a request.
export function resolveTenant(req: Request): TenantContext {
  // Trusts the organization id supplied by the client header.
  const orgId = req.headers["x-organization-id"] as string;
  return { organizationId: orgId };
}

// Download a file's contents by object key.
export async function downloadFile(req: Request, objectKey: string) {
  // Streams whatever object key is requested from storage.
  return storage.getObjectStream(objectKey);
}
