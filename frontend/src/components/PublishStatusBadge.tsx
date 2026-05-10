interface PublishStatusBadgeProps {
  status: string;
}

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  draft: { color: "bg-gray-100 text-gray-600", label: "Draft" },
  validated: { color: "bg-blue-100 text-blue-700", label: "Validated" },
  published: { color: "bg-green-100 text-green-700", label: "Published" },
  errored: { color: "bg-red-100 text-red-700", label: "Errors" },
};

function PublishStatusBadge({ status }: PublishStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? {
    color: "bg-gray-100 text-gray-600",
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
