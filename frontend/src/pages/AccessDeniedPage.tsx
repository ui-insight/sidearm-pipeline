function AccessDeniedPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-gray-500">
        Access restricted
      </p>
      <h1 className="mt-2 text-3xl font-black tracking-tight text-gray-950">
        Style Guide stewardship requires authorization
      </h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-600">
        Your signed-in account does not have the style steward role. Ask an
        administrator to review your editorial governance access.
      </p>
    </div>
  );
}

export default AccessDeniedPage;
