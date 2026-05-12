interface PublishStatusBadgeProps {
  status: string;
}

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  draft: { color: "bg-gray-100 text-gray-700 ring-1 ring-gray-200", label: "Draft" },
  validated: { color: "bg-blue-50 text-blue-700 ring-1 ring-blue-200", label: "Validated" },
  published: { color: "bg-green-50 text-green-700 ring-1 ring-green-200", label: "Published" },
  errored: { color: "bg-red-50 text-red-700 ring-1 ring-red-200", label: "Errors" },
};

function PublishStatusBadge({ status }: PublishStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? {
    color: "bg-gray-100 text-gray-700 ring-1 ring-gray-200",
    label: status,
  };

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${config.color}`}
    >
      {config.label}
    </span>
  );
}

export default PublishStatusBadge;
