@Controller("employees/:employeeId/documents")
export class DocumentsController {
  constructor(private readonly documents: DocumentsService) {}

  @Get()
  @RequireAnyPermission("employee.profile.read", "employee.contract.dispatch", "employee.contract.confirm")
  async list(@Req() req: Request, @Param("employeeId") employeeId: string, @Query() q: DocumentQuery) {
    const session = getSession(req);
    const minimal = q.contractMinimal === "true";
    if (minimal || !(await this.documents.canReadProfile(session, employeeId))) {
      // Different response shape for single-permission users.
      return this.documents.listContractMinimal(session, employeeId);
    }
    return this.documents.list(session, employeeId, q);
  }

  @Post(":documentId/dispatch")
  @RequirePermission("employee.contract.dispatch")
  dispatch(@Req() req: Request, @Param() p: DocParams, @Headers("idempotency-key") key: string) {
    return this.documents.dispatch(getSession(req), p, key);
  }

  @Post(":documentId/confirm")
  @RequirePermission("employee.contract.confirm")
  confirm(@Req() req: Request, @Param() p: DocParams, @Headers("idempotency-key") key: string) {
    return this.documents.confirm(getSession(req), p, key);
  }
}

// contract-minimal-view.ts
export type ContractMinimalView = {
  employeeId: string;
  displayName: string;
  contract: { id: string; state: "draft" | "sent" | "signed_uploaded" | "confirmed"; sentAt?: string };
  canDispatch: boolean;
  canConfirm: boolean;
};
