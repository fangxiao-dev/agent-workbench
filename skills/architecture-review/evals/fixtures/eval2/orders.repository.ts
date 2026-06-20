import { db } from "./db";

// Orders are tenant-owned: every row has organization_id.
export class OrdersRepository {
  async list(orgId: string) {
    return db.order.findMany({ where: { organizationId: orgId } });
  }

  async detail(orgId: string, id: string) {
    return db.order.findFirst({ where: { id, organizationId: orgId } });
  }

  // Dashboard widget: total revenue + order count, used on the stats page.
  async getStats() {
    const [row] = await db.$queryRawUnsafe<StatsRow[]>(
      `SELECT count(*) AS orders, coalesce(sum(total_amount), 0) AS revenue
         FROM orders`,
    );
    return row;
  }
}
