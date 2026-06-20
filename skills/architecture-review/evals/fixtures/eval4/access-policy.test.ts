import { canReadDocument } from "./access-policy";

test("allows a grantee with an active temporary grant", () => {
  const now = new Date("2026-06-20T10:00:00Z");
  const document = { id: "doc_1", ownerUserId: "user_owner" };
  const grants = [
    {
      documentId: "doc_1",
      granteeUserId: "user_reviewer",
      expiresAt: new Date("2026-06-20T11:00:00Z"),
      revokedAt: null,
    },
  ];

  expect(canReadDocument("user_reviewer", document, grants, now)).toBe(true);
});
