// staff-page.tsx — staff page shell
export function StaffPage({ session, units }: Props) {
  const profileUnits = units.filter((u) => canAccessScope(session, "employee.profile.read", u.id));
  const contractOnlyUnits = units.filter(
    (u) =>
      !profileUnits.includes(u) &&
      (canAccessScope(session, "employee.contract.dispatch", u.id) ||
        canAccessScope(session, "employee.contract.confirm", u.id))
  );
  return (
    <>
      {profileUnits.length > 0 && <EmployeeRoster units={profileUnits} />}
      {/* Users with mixed permissions across stores see both lists. */}
      {contractOnlyUnits.length > 0 && <ContractTasksMinimal units={contractOnlyUnits} />}
    </>
  );
}

// contract-section.tsx (used inside EmployeeRoster detail) — full flow
export function ContractSection({ employeeId }: { employeeId: string }) {
  const docs = useDocuments(employeeId);
  const dispatch = useDispatchContract(employeeId); // idempotency key per click, 409 replay handling
  const upload = useSignedUpload(employeeId);       // presigned upload, expiry + 412 handling
  const confirm = useConfirmContract(employeeId);
  return <ContractFlow docs={docs.data} onDispatch={dispatch} onUpload={upload} onConfirm={confirm} />;
}

// contract-tasks-minimal.tsx — 448 lines in the real PR; abbreviated
export function ContractTasksMinimal({ units }: { units: Unit[] }) {
  const rows = useMinimalContractTasks(units);       // calls ?contractMinimal=true per employee
  const dispatch = useMinimalDispatch();              // own idempotency + replay handling
  const upload = useMinimalSignedUpload();            // own presigned upload, expiry + 412 handling
  const confirm = useMinimalConfirm();
  return <MinimalContractTable rows={rows} onDispatch={dispatch} onUpload={upload} onConfirm={confirm} />;
}
