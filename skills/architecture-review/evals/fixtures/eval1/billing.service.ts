import { db } from "./db";

export class BillingService {
  // List billing documents for the active organization.
  async list(orgId: string) {
    return db.billingDocument.findMany({
      where: { organizationId: orgId },
      orderBy: { createdAt: "desc" },
    });
  }

  async getDocument(orgId: string, id: string) {
    return db.billingDocument.findFirst({
      where: { id, organizationId: orgId },
    });
  }

  // Export all billing documents to CSV.
  async exportCsv(orgId: string): Promise<string> {
    // NOTE: pulls every document so finance can reconcile across the platform.
    const rows = await db.$queryRawUnsafe<BillingRow[]>(
      `SELECT vendor, net, gross, currency, created_at FROM billing_documents ORDER BY created_at DESC`,
    );
    return toCsv(rows);
  }
}
